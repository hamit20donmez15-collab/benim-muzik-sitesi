import os
import json
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import yt_dlp
from waitress import serve

app = Flask(__name__, template_folder='.', static_folder='.')
CORS(app)

SONGS_FILE = 'songs.json'
DOWNLOAD_DIR = 'downloads'
ADMIN_PASSWORD = "182015hd"

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

def load_songs():
    if os.path.exists(SONGS_FILE):
        try:
            with open(SONGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_songs(songs):
    with open(SONGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(songs, f, ensure_ascii=False, indent=4)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    if data.get('password') == ADMIN_PASSWORD:
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Hatalı şifre!'}), 401

@app.route('/api/songs', methods=['GET'])
def get_songs():
    return jsonify(load_songs())

# YouTube'da arama yapıp şarkı listesi getiren uç nokta (Örn: "Manifest")
@app.route('/api/search-youtube', methods=['POST'])
def search_youtube():
    data = request.get_json() or {}
    query = data.get('query')
    limit = int(data.get('limit', 10))
    if limit > 25:
        limit = 25

    if not query:
        return jsonify({'success': False, 'message': 'Arama terimi gerekli!'}), 400

    ydl_opts = {
        'extract_flat': True,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True
    }
    
    if os.path.exists('cookies.txt'):
        ydl_opts['cookiefile'] = 'cookies.txt'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # YouTube'da arama yapıp sonuçları toplar
            search_results = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
            entries = search_results.get('entries', [])
            
            results = []
            for entry in entries:
                results.append({
                    'id': entry.get('id'),
                    'title': entry.get('title'),
                    'url': f"https://www.youtube.com/watch?v={entry.get('id')}",
                    'duration': entry.get('duration', 0)
                })
            return jsonify({'success': True, 'results': results})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Seçilen YouTube linkini indirip arşive ekleyen uç nokta
@app.route('/api/download-song', methods=['POST'])
def download_song():
    data = request.get_json() or {}
    url = data.get('url')
    
    if not url:
        return jsonify({'success': False, 'message': 'URL gerekli!'}), 400

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True
    }

    if os.path.exists('cookies.txt'):
        ydl_opts['cookiefile'] = 'cookies.txt'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = str(info.get('id'))
            filename = f"{video_id}.mp3"
            
            song_data = {
                'id': video_id,
                'title': info.get('title', 'Bilinmeyen Şarkı'),
                'artist': info.get('uploader', 'Bilinmeyen Sanatçı'),
                'url': f'/downloads/{filename}',
                'filename': filename,
                'duration': info.get('duration', 0)
            }

            songs = load_songs()
            songs = [s for s in songs if s.get('id') != song_data['id']]
            songs.append(song_data)
            save_songs(songs)

            return jsonify({'success': True, 'song': song_data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/delete-song/<song_id>', methods=['DELETE'])
def delete_song(song_id):
    songs = load_songs()
    updated_songs = []
    deleted = False

    for song in songs:
        if str(song.get('id')) == str(song_id):
            deleted = True
            filepath = os.path.join(DOWNLOAD_DIR, song.get('filename', ''))
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except:
                    pass
        else:
            updated_songs.append(song)

    if deleted:
        save_songs(updated_songs)
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Şarkı bulunamadı'}), 404

@app.route('/downloads/<filename>')
def download_file(filename):
    return send_from_directory(DOWNLOAD_DIR, filename)

@app.route('/favicon.ico')
def favicon():
    return '', 204

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    serve(app, host='0.0.0.0', port=port)
