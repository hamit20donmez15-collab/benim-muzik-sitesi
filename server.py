import os
import json
import logging
import yt_dlp
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from waitress import serve

logging.basicConfig(level=logging.INFO)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'downloads')
SONGS_JSON = os.path.join(BASE_DIR, 'songs.json')
ADMIN_PASSWORD = "182015hd"

app = Flask(__name__, static_folder=BASE_DIR, template_folder=BASE_DIR)
CORS(app)

os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_songs():
    if not os.path.exists(SONGS_JSON):
        return []
    try:
        with open(SONGS_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

def save_songs(songs):
    with open(SONGS_JSON, 'w', encoding='utf-8') as f:
        json.dump(songs, f, ensure_ascii=False, indent=4)

@app.route('/')
def serve_index():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/admin')
def serve_admin():
    return send_from_directory(BASE_DIR, 'admin.html')

@app.route('/downloads/<path:filename>')
def serve_downloads(filename):
    return send_from_directory(OUTPUT_DIR, filename)

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json() or {}
    if data.get('password') == ADMIN_PASSWORD:
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Hatalı şifre!'}), 401

@app.route('/api/songs', methods=['GET'])
def api_get_songs():
    return jsonify(load_songs())

@app.route('/api/artists', methods=['GET'])
def api_get_artists():
    songs = load_songs()
    artists = list(set(s.get('artist', 'Bilinmiyor') for s in songs if s.get('artist')))
    return jsonify(artists)

@app.route('/api/search_youtube', methods=['GET'])
def search_youtube():
    query = request.args.get('q')
    if not query:
        return jsonify({'error': 'Arama terimi girilmedi.'}), 400
    
    ydl_opts = {'format': 'bestaudio/best', 'quiet': True, 'default_search': 'ytsearch1'}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            if 'entries' in info and len(info['entries']) > 0:
                video = info['entries'][0]
            else:
                video = info
            return jsonify({
                'title': video.get('title'),
                'url': video.get('webpage_url'),
                'thumbnail': video.get('thumbnail')
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/fetch_results', methods=['POST'])
def fetch_results():
    data = request.get_json() or {}
    query = data.get('query')
    limit = int(data.get('limit', 15))

    if not query:
        return jsonify({'error': 'Arama terimi gereklidir.'}), 400

    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'default_search': f'ytsearch{limit}'
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            entries = info.get('entries', [])
            if not entries and 'title' in info:
                entries = [info]

            results = []
            for entry in entries:
                if not entry:
                    continue
                results.append({
                    'title': entry.get('title', 'Bilinmeyen Şarkı'),
                    'url': entry.get('webpage_url') or f"https://www.youtube.com/watch?v={entry.get('id')}",
                    'thumbnail': entry.get('thumbnail')
                })
            return jsonify({'success': True, 'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download_batch', methods=['POST'])
def download_batch():
    data = request.get_json() or {}
    selected_songs = data.get('songs', [])
    artist_name = data.get('artist', 'Bilinmiyor')

    if not selected_songs:
        return jsonify({'error': 'Hiç şarkı seçilmedi.'}), 400

    songs = load_songs()
    next_id = max([s.get('id', 0) for s in songs], default=0) + 1
    added_songs = []

    for item in selected_songs:
        video_url = item.get('url')
        video_title = item.get('title')

        if not video_url or not video_title:
            continue

        dl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(OUTPUT_DIR, '%(title).50s.%(ext)s'),
            'restrictfilenames': True,
            'quiet': True
        }

        try:
            with yt_dlp.YoutubeDL(dl_opts) as downloader:
                res_info = downloader.extract_info(video_url, download=True)
                base_path = downloader.prepare_filename(res_info)
                filename = os.path.basename(base_path)

                new_song = {
                    'id': next_id,
                    'title': video_title,
                    'artist': artist_name,
                    'file': filename
                }
                songs.append(new_song)
                added_songs.append(new_song)
                next_id += 1
        except Exception as e:
            logging.error(f"İndirme hatası ({video_title}): {str(e)}")
            continue

    save_songs(songs)
    return jsonify({'success': True, 'added': added_songs})

@app.route('/api/download', methods=['POST'])
def download_audio():
    data = request.get_json() or {}
    url = data.get('url')
    if not url:
        return jsonify({'error': 'URL bulunamadı.'}), 400

    outtmpl = os.path.join(OUTPUT_DIR, '%(title).50s.%(ext)s')
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': outtmpl,
        'restrictfilenames': True,
        'quiet': True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            base_path = ydl.prepare_filename(info)
            filename = os.path.basename(base_path)
            return jsonify({'success': True, 'file': filename})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/publish', methods=['POST'])
def publish_song():
    data = request.get_json() or {}
    title = data.get('title')
    file_name = data.get('file')
    artist = data.get('artist', 'Bilinmiyor')

    if not title or not file_name:
        return jsonify({'error': 'Eksik bilgi.'}), 400

    songs = load_songs()
    new_id = max([s.get('id', 0) for s in songs], default=0) + 1
    new_song = {'id': new_id, 'title': title, 'artist': artist, 'file': file_name}
    songs.append(new_song)
    save_songs(songs)

    return jsonify({'success': True, 'song': new_song})

if __name__ == '__main__':
    print("--------------------------------------------------")
    print("Müzik Kütüphanesi Başlatıldı!")
    print("Site adresi: http://localhost:5000")
    print("Yönetici paneli: http://localhost:5000/admin")
    print("--------------------------------------------------")
    serve(app, host='0.0.0.0', port=5000)