import yt_dlp
import os
import json
from datetime import datetime

class DownloadWorker:
    def __init__(self):
        self.download_dir = "downloads"
        self.log_dir = "logs"
        self.db_path = "songs.json"
        self.cookie_path = "cookies.txt"
        
        os.makedirs(self.download_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)

    def log(self, message):
        log_file = os.path.join(self.log_dir, f"download_{datetime.now().strftime('%Y%m%d')}.log")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now()}] {message}\n")

    def update_database(self, song_info):
        songs = []
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    songs = json.load(f)
            except:
                pass
        
        songs.insert(0, song_info)
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(songs, f, ensure_ascii=False, indent=2)

    def download_mp3(self, url):
        try:
            ydl_opts = {
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
                "outtmpl": os.path.join(self.download_dir, "%(title)s.%(ext)s"),
                "quiet": True,
                "no_warnings": True,
            }

            if os.path.exists(self.cookie_path):
                ydl_opts["cookiefile"] = self.cookie_path

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = f"{info['title']}.mp3"
                file_path = os.path.join(self.download_dir, filename)
                
                song_data = {
                    "id": info["id"],
                    "title": info["title"],
                    "uploader": info.get("uploader", "Bilinmiyor"),
                    "duration": info.get("duration", 0),
                    "filename": filename,
                    "url": url,
                    "download_date": datetime.now().strftime("%d.%m.%Y %H:%M")
                }
                
                self.update_database(song_data)
                self.log(f"BAŞARILI: {filename} indirildi")
                return {"status": "success", "data": song_data}

        except Exception as e:
            self.log(f"HATA: {str(e)}")
            return {"status": "error", "message": str(e)}

    def search(self, query):
        try:
            ydl_opts = {
                "default_search": "ytsearch10",
                "quiet": True,
                "no_warnings": True,
            }
            if os.path.exists(self.cookie_path):
                ydl_opts["cookiefile"] = self.cookie_path

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                results = ydl.extract_info(query, download=False)
                items = []
                for entry in results["entries"]:
                    items.append({
                        "id": entry["id"],
                        "title": entry["title"],
                        "uploader": entry.get("uploader", ""),
                        "duration": entry.get("duration", 0),
                        "url": entry["webpage_url"],
                        "thumbnail": entry.get("thumbnail", "")
                    })
                return {"status": "success", "results": items}

        except Exception as e:
            self.log(f"ARAMA HATASI: {str(e)}")
            return {"status": "error", "message": str(e)}
