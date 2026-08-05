"""
=============================================================================
YOUTUBE MP3 İNDİRME SUNUCUSU - GELİŞMİŞ VERSİYON
=============================================================================
Bu dosya, sunucunun daha kararlı çalışması, hataların yakalanması,
loglanması ve YouTube bot korumalarının aşılması için özel olarak
genişletilmiş ve detaylandırılmıştır.
=============================================================================
"""

import os
import sys
import json
import glob
import time
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, request, jsonify, send_from_directory, abort
from flask_cors import CORS
import yt_dlp
from waitress import serve

# ============================================================================
# 1. YAPILANDIRMA VE AYARLAR
# ============================================================================

class ServerConfig:
    """Sunucu için gerekli tüm ayarların tutulduğu ana sınıf."""
    SONGS_FILE = 'songs.json'
    DOWNLOAD_DIR = 'downloads'
    LOG_DIR = 'logs'
    ADMIN_PASSWORD = "182015hd"
    MAX_SEARCH_LIMIT = 25
    DEFAULT_SEARCH_LIMIT = 10
    PORT = int(os.environ.get("PORT", 5000))
    DEBUG_MODE = False

# ============================================================================
# 2. GELİŞMİŞ LOGLAMA (KAYIT) SİSTEMİ
# ============================================================================

def setup_logging():
    """Sistemdeki tüm hareketleri ve hataları bir dosyaya kaydeder."""
    if not os.path.exists(ServerConfig.LOG_DIR):
        os.makedirs(ServerConfig.LOG_DIR)

    log_file = os.path.join(ServerConfig.LOG_DIR, 'server.log')
    
    logger = logging.getLogger('MusicServer')
    logger.setLevel(logging.DEBUG)

    # Dosyaya yazma ayarı (Maksimum 5 MB, 3 yedek)
    file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)

    # Konsola (Render terminaline) yazma ayarı
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    # Log formatı
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()
logger.info("Sunucu başlatılıyor... Gelişmiş sistem devrede.")

# ============================================================================
# 3. YARDIMCI SINIFLAR VE YÖNETİCİLER
# ============================================================================

class FileManager:
    """Dosya okuma, yazma ve silme işlemlerini güvenli hale getiren sınıf."""
    
    @staticmethod
    def ensure_directories():
        """Gerekli klasörlerin var olup olmadığını kontrol eder, yoksa oluşturur."""
        logger.info("Klasörler kontrol ediliyor...")
        dirs_to_check = [ServerConfig.DOWNLOAD_DIR, ServerConfig.LOG_DIR]
        for directory in dirs_to_check:
            if not os.path.exists(directory):
                try:
                    os.makedirs(directory)
                    logger.info(f"Yeni klasör oluşturuldu: {directory}")
                except Exception as e:
                    logger.error(f"Klasör oluşturulamadı ({directory}): {str(e)}")

    @staticmethod
    def load_songs():
        """Şarkı veri tabanını (JSON) okur ve güvenli bir şekilde döndürür."""
        if not os.path.exists(ServerConfig.SONGS_FILE):
            logger.warning(f"Veri tabanı dosyası ({ServerConfig.SONGS_FILE}) bulunamadı. Yeni bir tane oluşturuluyor.")
            FileManager.save_songs([])
            return []
            
        try:
            with open(ServerConfig.SONGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not isinstance(data, list):
                    logger.warning("Veri tabanı bozuk. Liste formatına sıfırlanıyor.")
                    return []
                return data
        except json.JSONDecodeError:
            logger.error("JSON okuma hatası! Dosya bozuk. Sıfırlanıyor.")
            return []
        except Exception as e:
            logger.critical(f"Beklenmeyen dosya okuma hatası: {str(e)}")
            return []

    @staticmethod
    def save_songs(songs_list):
        """Şarkı listesini JSON dosyasına güvenli bir şekilde yazar."""
        try:
            with open(ServerConfig.SONGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(songs_list, f, ensure_ascii=False, indent=4)
            logger.debug(f"Veri tabanı güncellendi. Toplam kayıt: {len(songs_list)}")
            return True
        except Exception as e:
            logger.error(f"Dosya yazma hatası: {str(e)}")
            return False

# Dosya sistemini hazırla
FileManager.ensure_directories()

# ============================================================================
# 4. YOUTUBE-DLP ÖZEL ADAPTASYONLARI
# ============================================================================

class YTDLpCustomLogger:
    """yt-dlp içinden gelen mesajları kendi log sistemimize aktarır."""
    def debug(self, msg):
        if not msg.startswith('[debug] '):
            logger.debug(f"YT-DLP: {msg}")

    def info(self, msg):
        logger.info(f"YT-DLP: {msg}")

    def warning(self, msg):
        logger.warning(f"YT-DLP: {msg}")

    def error(self, msg):
        logger.error(f"YT-DLP HATA: {msg}")

def yt_dlp_progress_hook(d):
    """İndirme sırasında ilerlemeyi takip eder."""
    if d['status'] == 'downloading':
        try:
            percent = d.get('_percent_str', 'N/A')
            speed = d.get('_speed_str', 'N/A')
            logger.debug(f"İniyor... {percent} - Hız: {speed}")
        except:
            pass
    elif d['status'] == 'finished':
        logger.info(f"İndirme tamamlandı, işleniyor: {d.get('filename', 'Bilinmeyen Dosya')}")
    elif d['status'] == 'error':
        logger.error("İndirme sırasında kritik bir hata oluştu!")

# ============================================================================
# 5. FLASK UYGULAMASI VE İSKELETİ
# ============================================================================

app = Flask(__name__, template_folder='.', static_folder='.')
CORS(app)

# Flask'ın kendi iç loglarını temizle (bizimkiyle karışmasın)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# ============================================================================
# 6. API UÇ NOKTALARI (ENDPOINTS)
# ============================================================================

@app.route('/')
def index_page():
    """Ana sayfayı kullanıcıya sunar."""
    logger.info("Ana sayfaya giriş yapıldı.")
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"index.html yüklenirken hata: {str(e)}")
        return "Ana sayfa dosyası (index.html) bulunamadı veya bozuk.", 404

@app.route('/admin')
def admin_page():
    """Yönetici panelini sunar."""
    logger.info("Yönetici paneline erişim isteği.")
    try:
        return render_template('admin.html')
    except Exception as e:
        logger.error(f"admin.html yüklenirken hata: {str(e)}")
        return "Yönetici dosyası (admin.html) bulunamadı.", 404

@app.route('/api/login', methods=['POST'])
def handle_login():
    """Yönetici şifresini doğrular."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Veri alınamadı!'}), 400
            
        password = data.get('password', '')
        
        if password == ServerConfig.ADMIN_PASSWORD:
            logger.info("Başarılı yönetici girişi.")
            return jsonify({'success': True, 'message': 'Giriş başarılı.'})
        else:
            logger.warning(f"Hatalı şifre denemesi yapıldı. Girilen: {password}")
            return jsonify({'success': False, 'message': 'Hatalı şifre!'}), 401
            
    except Exception as e:
        logger.error(f"Giriş işlemi sırasında sistem hatası: {str(e)}")
        return jsonify({'success': False, 'message': 'Sistem hatası oluştu.'}), 500

@app.route('/api/songs', methods=['GET'])
def fetch_songs():
    """Mevcut şarkı kütüphanesini ön yüze gönderir."""
    logger.debug("Şarkı listesi talep edildi.")
    try:
        songs = FileManager.load_songs()
        return jsonify(songs)
    except Exception as e:
        logger.error(f"Şarkı listesi gönderilirken hata: {str(e)}")
        return jsonify([]), 500

@app.route('/api/search-youtube', methods=['POST'])
def search_youtube_videos():
    """
    YouTube üzerinde gelişmiş arama yapar.
    Hatalara karşı dayanıklıdır ve limit kontrolleri uygular.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Eksik veri gönderildi.'}), 400

        query = data.get('query', '').strip()
        limit = int(data.get('limit', ServerConfig.DEFAULT_SEARCH_LIMIT))
        
        # Limit kontrolü (İstemci tarafı bypass edilirse diye sunucu kontrolü)
        if limit > ServerConfig.MAX_SEARCH_LIMIT:
            logger.warning(f"Limit aşıldı ({limit}). {ServerConfig.MAX_SEARCH_LIMIT} değerine çekiliyor.")
            limit = ServerConfig.MAX_SEARCH_LIMIT
        if limit < 1:
            limit = 1

        if not query:
            return jsonify({'success': False, 'message': 'Arama terimi boş olamaz!'}), 400

        logger.info(f"YouTube araması başlatıldı. Terim: '{query}', Limit: {limit}")

        # YT-DLP arama ayarları
        ydl_opts = {
            'extract_flat': True,  # Sadece meta veriyi al, videoyu indirme
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'logger': YTDLpCustomLogger(),
            'ignoreerrors': True, # Hatalı videoları atla, çökmeyi engelle
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        }
        
        # Eğer çerez dosyası varsa ekle (Bot engeli için kritik)
        if os.path.exists('cookies.txt'):
            logger.info("cookies.txt bulundu ve aramaya dahil ediliyor.")
            ydl_opts['cookiefile'] = 'cookies.txt'
        else:
            logger.warning("cookies.txt bulunamadı! Arama YouTube tarafından engellenebilir.")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # ytsearch formatı ile arama yapılıyor
            search_string = f"ytsearch{limit}:{query}"
            search_results = ydl.extract_info(search_string, download=False)
            
            if not search_results or 'entries' not in search_results:
                logger.warning(f"Arama sonucu bulunamadı: {query}")
                return jsonify({'success': True, 'results': []})

            entries = search_results.get('entries', [])
            results = []
            
            # Gelen sonuçları temizle ve hazırla
            for entry in entries:
                if entry: # Entry null değilse
                    results.append({
                        'id': entry.get('id', ''),
                        'title': entry.get('title', 'Başlıksız Video'),
                        'channel': entry.get('uploader', 'Bilinmeyen Kanal'),
                        'url': f"https://www.youtube.com/watch?v={entry.get('id', '')}"
                    })
                    
            logger.info(f"Arama başarılı. {len(results)} sonuç bulundu.")
            return jsonify({'success': True, 'results': results})

    except Exception as e:
        logger.critical(f"Arama motorunda kritik hata: {str(e)}")
        return jsonify({'success': False, 'message': f'Sunucu içi arama hatası: {str(e)}'}), 500

@app.route('/api/download-song', methods=['POST'])
def download_youtube_song():
    """
    Belirtilen YouTube URL'sini indirir.
    FFmpeg gerektirmeyen (bestaudio) güvenli format kullanılır.
    Çift kayıtları engeller ve güvenli dosya isimleri oluşturur.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Eksik istek!'}), 400

        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({'success': False, 'message': 'URL adresi gerekli!'}), 400

        logger.info(f"İndirme isteği alındı. URL: {url}")

        # FFmpeg olmadan en iyi sesi indirmek için özel ayarlar
        ydl_opts = {
            'format': 'bestaudio', # Sadece sesi indir
            'outtmpl': os.path.join(ServerConfig.DOWNLOAD_DIR, '%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'logger': YTDLpCustomLogger(),
            'progress_hooks': [yt_dlp_progress_hook],
            'ignoreerrors': False,
            'geo_bypass': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        }

        # Çerez kontrolü
        if os.path.exists('cookies.txt'):
            ydl_opts['cookiefile'] = 'cookies.txt'

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info("Video meta verileri çıkarılıyor...")
            info = ydl.extract_info(url, download=True)
            
            video_id = str(info.get('id', 'unknown'))
            # Format neyse (m4a, webm vb.) onu al, FFmpeg zorunluluğunu kaldır.
            ext = info.get('ext', 'm4a') 
            filename = f"{video_id}.{ext}"
            
            # Güvenli JSON objesi
            song_data = {
                'id': video_id,
                'title': info.get('title', 'Bilinmeyen Şarkı'),
                'artist': info.get('uploader', 'Bilinmeyen Sanatçı'),
                'url': f'/downloads/{filename}',
                'filename': filename
            }

            logger.info(f"İndirme başarılı: {song_data['title']}")

            # Veritabanını güncelle (Aynı şarkı varsa önce eskisini listeden çıkar)
            songs = FileManager.load_songs()
            songs = [s for s in songs if str(s.get('id')) != video_id]
            songs.append(song_data)
            
            if FileManager.save_songs(songs):
                logger.info("Şarkı veri tabanına başarıyla eklendi.")
                return jsonify({'success': True, 'song': song_data})
            else:
                logger.error("Şarkı indi fakat veritabanına kaydedilemedi!")
                return jsonify({'success': False, 'message': 'Dosya indi ama kaydedilemedi.'}), 500

    except Exception as e:
        error_msg = str(e)
        logger.error(f"İndirme motoru çöktü: {error_msg}")
        return jsonify({'success': False, 'message': 'İndirme engellendi veya hata oluştu.'}), 500

@app.route('/api/delete-song/<song_id>', methods=['DELETE'])
def remove_song(song_id):
    """Belirtilen şarkıyı listeden ve sunucu klasöründen kalıcı olarak siler."""
    logger.info(f"Silme isteği: ID = {song_id}")
    try:
        songs = FileManager.load_songs()
        
        # Silinmeyecek olanları filtrele
        updated_songs = [s for s in songs if str(s.get('id')) != str(song_id)]
        
        # Fiziksel dosyayı bul ve yok et
        for song in songs:
            if str(song.get('id')) == str(song_id):
                filepath = os.path.join(ServerConfig.DOWNLOAD_DIR, song.get('filename', ''))
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                        logger.info(f"Fiziksel dosya silindi: {filepath}")
                    except Exception as e:
                        logger.warning(f"Fiziksel dosya silinemedi ({filepath}): {str(e)}")
                else:
                    logger.warning(f"Dosya zaten klasörde yok: {filepath}")
                    
        FileManager.save_songs(updated_songs)
        logger.info(f"Şarkı ({song_id}) veri tabanından çıkarıldı.")
        return jsonify({'success': True, 'message': 'Şarkı başarıyla silindi.'})
        
    except Exception as e:
        logger.error(f"Silme işlemi sırasında hata: {str(e)}")
        return jsonify({'success': False, 'message': 'Silme işlemi başarısız oldu.'}), 500

@app.route('/api/clear-all', methods=['DELETE'])
def factory_reset():
    """Tüm kütüphaneyi ve inen dosyaları temizler (Nükleer Seçenek)."""
    logger.warning("NÜKLEER SIFIRLAMA BAŞLATILDI!")
    try:
        # JSON dosyasını sıfırla
        FileManager.save_songs([])
        logger.info("JSON veri tabanı temizlendi.")
        
        # Fiziksel dosyaları klasörden sil
        files = glob.glob(os.path.join(ServerConfig.DOWNLOAD_DIR, '*'))
        deleted_count = 0
        for f in files:
            try:
                os.remove(f)
                deleted_count += 1
            except Exception as e:
                logger.error(f"Silinemeyen dosya ({f}): {str(e)}")
                
        logger.info(f"Sıfırlama tamamlandı. Toplam silinen fiziksel dosya: {deleted_count}")
        return jsonify({'success': True, 'message': 'Tüm arşiv ve dosyalar sıfırlandı!'})
        
    except Exception as e:
        logger.critical(f"Sıfırlama sırasında kritik hata: {str(e)}")
        return jsonify({'success': False, 'message': 'Sıfırlama işlemi başarısız.'}), 500

@app.route('/downloads/<filename>')
def serve_audio_file(filename):
    """İndirilen medya dosyalarını istemciye (tarayıcıya/oynatıcıya) güvenli şekilde sunar."""
    try:
        # Klasör dışına çıkmayı engelleyen temel güvenlik önlemi
        if '..' in filename or '/' in filename:
            logger.warning(f"Zararlı dosya erişim girişimi: {filename}")
            abort(403)
            
        logger.debug(f"Dosya sunuluyor: {filename}")
        return send_from_directory(ServerConfig.DOWNLOAD_DIR, filename)
    except Exception as e:
        logger.error(f"Dosya sunulurken hata oluştu ({filename}): {str(e)}")
        abort(404)

@app.route('/favicon.ico')
def favicon_handler():
    """Tarayıcıların gereksiz favicon isteklerini sessizce yanıtlar."""
    return '', 204

# ============================================================================
# 7. SUNUCUYU BAŞLATMA BLOĞU
# ============================================================================

if __name__ == '__main__':
    """
    Render gibi platformlar port numarasını otomatik belirler.
    Waitress kullanarak üretim (production) kalitesinde sunucu ayağa kaldırılır.
    """
    logger.info(f"Sunucu {ServerConfig.PORT} portu üzerinde ayağa kaldırılıyor...")
    try:
        # Flask'ın geliştirme sunucusu yerine güçlü Waitress sunucusunu kullan
        serve(app, host='0.0.0.0', port=ServerConfig.PORT, threads=4)
    except Exception as e:
        logger.critical(f"Sunucu başlatılamadı: {str(e)}")
