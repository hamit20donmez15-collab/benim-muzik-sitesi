import os
import yt_dlp
import logging

# Arka plan işleyicisi için log ayarı
logging.basicConfig(level=logging.INFO, format='%(asctime)s - WORKER - %(levelname)s - %(message)s')

class BackgroundDownloader:
    """Arka planda terminal açmadan YouTube indirme işlemlerini yöneten sınıf."""
    
    @staticmethod
    def download_audio(url, download_dir='downloads'):
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)

        ydl_opts = {
            'outtmpl': os.path.join(download_dir, '%(id)s.%(ext)s'),
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        }
        
        if os.path.exists('cookies.txt'):
            ydl_opts['cookiefile'] = 'cookies.txt'

        logging.info(f"Arka plan worker'ı indirmeyi başlatıyor: {url}")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                video_id = str(info.get('id', 'unknown'))
                filename = f"{video_id}.mp3"
                
                return {
                    'success': True,
                    'id': video_id,
                    'title': info.get('title', 'Bilinmeyen Şarkı'),
                    'artist': info.get('uploader', 'Bilinmeyen Sanatçı'),
                    'url': f'/downloads/{filename}',
                    'filename': filename
                }
        except Exception as e:
            logging.error(f"Worker indirme hatası: {str(e)}")
            return {'success': False, 'message': str(e)}
