import os
import sys
import json
import glob
import logging
from flask import Flask, render_template, request, jsonify, send_from_directory, abort
from flask_cors import CORS
import yt_dlp
from waitress import serve

# --- YAPILANDIRMA ---
PORT = int(os.environ.get("PORT", 5000))
SONGS_FILE = 'songs.json'
DOWNLOAD_DIR = 'downloads'

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

app = Flask(__name__, template_folder='.', static_folder='.')
CORS(app)

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

def load_songs():
    if not os.path.exists(SONGS_FILE):
        return []
    try:
        with open(SONGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_songs(songs_list):
    try:
        with open(SONGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(songs_list, f, ensure_ascii=False, indent=4)
        return True
    except:
        return False

# --- SAYFALAR ---
@app.route('/')
def index_page():
    return render_template('index.html')

@app.route('/admin')
def admin_page():
    return render_template('admin.html')

# --- API UÇ NOKTALARI ---
@app.route('/api/login', methods=['POST'])
def handle_login():
    data = request.get_json()
    if data and data.get('password') == "182015hd":
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Hatalı şifre!'}), 401

@app.route('/api/songs', methods=['GET'])
def fetch_songs():
    return jsonify(load_songs())

@app.route('/api/search-youtube', methods=['POST'])
def search_youtube_videos():
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        if not query:
            return jsonify({'success': False, 'message': 'Boş arama yapılamaz!'}), 400

        ydl_opts = {
            'extract_flat': True,
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'ignoreerrors': True,
        }
        if os.path.exists('cookies.txt'):
            ydl_opts['cookiefile'] = 'cookies.txt'

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_results = ydl.extract_info(f"ytsearch10:{query}", download=False)
            results = []
            if search_results and 'entries' in search_results:
                for entry in search_results.get('entries', []):
                    if entry:
                        results.append({
                            'id': entry.get('id', ''),
                            'title': entry.get('title', 'Başlıksız'),
                            'channel': entry.get('uploader', 'Bilinmeyen'),
                            'url': f"https://www.youtube.com/watch?v={entry.get('id', '')}"
                        })
            return jsonify({'success': True, 'results': results})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/download-song', methods=['POST'])
def download_youtube_song():
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        if not url:
            return jsonify({'success': False, 'message': 'URL gerekli!'}), 400

        ydl_opts = {
            'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
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

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = str(info.get('id', 'unknown'))
            filename = f"{video_id}.mp3"
            
            song_data = {
                'id': video_id,
                'title': info.get('title', 'Bilinmeyen Şarkı'),
                'artist': info.get('uploader', 'Bilinmeyen Sanatçı'),
                'url': f'/downloads/{filename}',
                'filename': filename
            }

            songs = load_songs()
            songs = [s for s in songs if str(s.get('id')) != video_id]
            songs.append(song_data)
            save_songs(songs)
            
            return jsonify({'success': True, 'song': song_data})

    except Exception as e:
        return jsonify({'success': False, 'message': f'İndirme hatası: {str(e)}'}), 500

@app.route('/api/delete-song/<song_id>', methods=['DELETE'])
def remove_song(song_id):
    songs = load_songs()
    updated = [s for s in songs if str(s.get('id')) != str(song_id)]
    for song in songs:
        if str(song.get('id')) == str(song_id):
            fp = os.path.join(DOWNLOAD_DIR, song.get('filename', ''))
            if os.path.exists(fp):
                os.remove(fp)
    save_songs(updated)
    return jsonify({'success': True})

@app.route('/api/clear-all', methods=['DELETE'])
def factory_reset():
    save_songs([])
    for f in glob.glob(os.path.join(DOWNLOAD_DIR, '*')):
        try: os.remove(f)
        except: pass
    return jsonify({'success': True})

@app.route('/downloads/<filename>')
def serve_audio_file(filename):
    if '..' in filename or '/' in filename:
        abort(403)
    return send_from_directory(DOWNLOAD_DIR, filename)

@app.route('/favicon.ico')
def favicon_handler():
    return '', 204

if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=PORT, threads=4)
