"""
=============================================================================
YOUTUBE MP3 VE VİDEO İNDİRME SUNUCUSU - ENTEGRE VERSİYON
=============================================================================
"""

import os
import sys
import json
import glob
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
    SONGS_FILE = 'songs.json'
    DOWNLOAD_DIR = 'downloads'
    LOG_DIR = 'logs'
    ADMIN_PASSWORD = "182015hd"
    MAX_SEARCH_LIMIT = 25
    DEFAULT_SEARCH_LIMIT = 10
    PORT = int(os.environ.get("PORT", 5000))
    DEBUG_MODE = False

# ============================================================================
# 2. LOGLAMA SİSTEMİ
# ============================================================================

def setup_logging():
    if not os.path.exists(ServerConfig.LOG_DIR):
        os.makedirs(ServerConfig.LOG_DIR)

    log_file = os.path.join(ServerConfig.LOG_DIR, 'server.log')
    
    logger = logging.getLogger('MusicServer')
    logger.setLevel(logging.DEBUG)

    file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()
logger.info("Sunucu başlatılıyor... Entegre mod devrede.")

# ============================================================================
# 3. DOSYA VE VERİ YÖNETİMİ
# ============================================================================

class FileManager:
    @staticmethod
    def ensure_directories():
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
        if not os.path.exists(ServerConfig.SONGS_FILE):
            FileManager.save_songs([])
            return []
            
        try:
            with open(ServerConfig.SONGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not isinstance(data, list):
                    return []
                return data
        except Exception:
            return []

    @staticmethod
    def save_songs(songs_list):
        try:
            with open(ServerConfig.SONGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(songs_list, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            logger.error(f"Dosya yazma hatası: {str(e)}")
            return False

FileManager.ensure_directories()

# ============================================================================
# 4. FLASK UYGULAMASI
# ============================================================================

app = Flask(__name__, template_folder='.', static_folder='.')
CORS(app)

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# ============================================================================
# 5. API UÇ NOKTALARI
# ============================================================================

@app.route('/')
def index_page():
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"index.html yüklenirken hata: {str(e)}")
        return "Ana sayfa bulunamadı.", 404

@app.route('/admin')
def admin_page():
    try:
        return render_template('admin.html')
    except Exception as e:
        logger.error(f"admin.html yüklenirken hata: {str(e)}")
        return "Yönetici paneli bulunamadı.", 404

@app.route('/api/login', methods=['POST'])
def handle_login():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Veri alınamadı!'}), 400
            
        if data.get('password', '') == ServerConfig.ADMIN_PASSWORD:
            return jsonify({'success': True, 'message': 'Giriş başarılı.'})
        return jsonify({'success': False, 'message': 'Hatalı şifre!'}), 401
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/songs', methods=['GET'])
def fetch_songs():
    return jsonify(FileManager.load_songs())

@app.route('/api/search-youtube', methods=['POST'])
def search_youtube_videos():
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        limit = int(data.get('limit', ServerConfig.DEFAULT_SEARCH_LIMIT))
        
        if limit > ServerConfig.MAX_SEARCH_LIMIT:
            limit = ServerConfig.MAX_SEARCH_LIMIT

        if not query:
            return jsonify({'success': False, 'message': 'Arama terimi boş olamaz!'}), 400

        ydl_opts = {
            'extract_flat': True,
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'ignoreerrors': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        }
        
        if os.path.exists('cookies.txt'):
            ydl_opts['cookiefile'] = 'cookies.txt'

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_results = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
            
            if not search_results or 'entries' not in search_results:
                return jsonify({'success': True, 'results': []})

            results = []
            for entry in search_results.get('entries', []):
                if entry:
                    results.append({
                        'id': entry.get('id', ''),
                        'title': entry.get('title', 'Başlıksız Video'),
                        'channel': entry.get('uploader', 'Bilinmeyen Kanal'),
                        'url': f"https://www.youtube.com/watch?v={entry.get('id', '')}"
                    })
                    
            return jsonify({'success': True, 'results': results})

    except Exception as e:
        logger.critical(f"Arama hatası: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/download-song', methods=['POST'])
def download_youtube_song():
    """
    Gönderdiğin masaüstü uygulamasındaki güvenli hata yakalama ve 
    ses işleme mantığı entegre edilmiştir.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Eksik istek!'}), 400

        url = data.get('url', '').strip()
        if not url:
            return jsonify({'success': False, 'message': 'URL adresi gerekli!'}), 400

        logger.info(f"İndirme isteği alındı: {url}")

        # Masaüstü kodundan ilham alınan ve web sunucusuna uyarlanan ayarlar
        ydl_opts = {
            'outtmpl': os.path.join(ServerConfig.DOWNLOAD_DIR, '%(id)s.%(ext)s'),
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'geo_bypass': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        }

        # Bot engeline karşı cookies.txt desteği
        if os.path.exists('cookies.txt'):
            ydl_opts['cookiefile'] = 'cookies.txt'
            logger.info("cookies.txt aktif olarak indirme işleminde kullanılıyor.")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
                if not info:
                    return jsonify({'success': False, 'message': 'Video bilgisi alınamadı!'}), 400
                
                video_id = str(info.get('id', 'unknown'))
                filename = f"{video_id}.mp3"
                
                song_data = {
                    'id': video_id,
                    'title': info.get('title', 'Bilinmeyen Şarkı'),
                    'artist': info.get('uploader', 'Bilinmeyen Sanatçı'),
                    'url': f'/downloads/{filename}',
                    'filename': filename
                }

                songs = FileManager.load_songs()
                songs = [s for s in songs if str(s.get('id')) != video_id]
                songs.append(song_data)
                
                if FileManager.save_songs(songs):
                    logger.info(f"İndirme ve kayıt başarılı: {song_data['title']}")
                    return jsonify({'success': True, 'song': song_data})
                else:
                    return jsonify({'success': False, 'message': 'Kayıt başarısız.'}), 500

            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)
                logger.error(f"YT-DLP İndirme Hatası: {error_msg}")
                if "Video unavailable" in error_msg or "Sign in to confirm" in error_msg:
                    return jsonify({'success': False, 'message': 'YouTube bot koruması veya video engeli oluştu. Lütfen cookies.txt dosyanızı kontrol edin.'}), 500
                return jsonify({'success': False, 'message': f'İndirme hatası: {error_msg[:150]}'}), 500

    except Exception as e:
        logger.error(f"Sunucu içi hata: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/delete-song/<song_id>', methods=['DELETE'])
def remove_song(song_id):
    try:
        songs = FileManager.load_songs()
        updated_songs = [s for s in songs if str(s.get('id')) != str(song_id)]
        
        for song in songs:
            if str(song.get('id')) == str(song_id):
                filepath = os.path.join(ServerConfig.DOWNLOAD_DIR, song.get('filename', ''))
                if os.path.exists(filepath):
                    os.remove(filepath)
                    
        FileManager.save_songs(updated_songs)
        return jsonify({'success': True, 'message': 'Şarkı silindi.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/clear-all', methods=['DELETE'])
def factory_reset():
    try:
        FileManager.save_songs([])
        for f in glob.glob(os.path.join(ServerConfig.DOWNLOAD_DIR, '*')):
            try:
                os.remove(f)
            except:
                pass
        return jsonify({'success': True, 'message': 'Arşiv sıfırlandı.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/downloads/<filename>')
def serve_audio_file(filename):
    try:
        if '..' in filename or '/' in filename:
            abort(403)
        return send_from_directory(ServerConfig.DOWNLOAD_DIR, filename)
    except Exception:
        abort(404)

@app.route('/favicon.ico')
def favicon_handler():
    return '', 204

# ============================================================================
# 6. BAŞLATMA
# ============================================================================

if __name__ == '__main__':
    logger.info(f"Sunucu {ServerConfig.PORT} portunda başlatılıyor...")
    serve(app, host='0.0.0.0', port=ServerConfig.PORT, threads=4)
