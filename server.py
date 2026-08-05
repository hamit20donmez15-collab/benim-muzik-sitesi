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
    password = data.get('password')
    if password == ADMIN_PASSWORD:
        return jsonify({'success': True, 'message': 'Giriş başarılı'})
    return jsonify({'success': False, 'message': 'Hatalı şifre!'}), 401

@app.route('/api/songs', methods=['GET'])
def get_songs():
    return jsonify(load_songs())

@app.route('/api/artists', methods=['GET'])
def get_artists():
    songs = load_songs()
    artists = list(set(song.get('artist', 'Bilinmeyen Sanatçı') for song in songs if song.get('artist')))
    return jsonify(artists)

@app.route('/api/add-song', methods=['POST'])
def add_song():
    data = request.get_json() or {}
    url = data.get('url')
    
    if not url:
        return jsonify({'success': False, 'message': 'URL gerekli!'}), 400

    # Render ortamında takılmaması için doğrudan ses akışını indirir
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            relative_filename = os.path.basename(filename)

            song_data = {
                'id': str(info.get('id', relative_filename)),
                'title': info.get('title', 'Bilinmeyen Şarkı'),
                'artist': info.get('uploader', 'Bilinmeyen Sanatçı'),
                'url': f'/downloads/{relative_filename}',
                'filename': relative_filename,
                'duration': info.get('duration', 0)
            }

            songs = load_songs()
            # Aynı şarkı daha önce eklenmişse güncelle
            songs = [s for s in songs if s.get('id') != song_data['id']]
            songs.append(song_data)
            save_songs(songs)

            return jsonify({'success': True, 'song': song_data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/delete-song/<song_id>', methods=['DELETE', 'POST'])
def delete_song(song_id):
    songs = load_songs()
    song_to_delete = None
    updated_songs = []

    for song in songs:
        if str(song.get('id')) == str(song_id) or song.get('title') == song_id:
            song_to_delete = song
        else:
            updated_songs.append(song)

    if song_to_delete:
        filename = song_to_delete.get('filename') or os.path.basename(song_to_delete.get('url', ''))
        filepath = os.path.join(DOWNLOAD_DIR, filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass
        
        save_songs(updated_songs)
        return jsonify({'success': True, 'message': 'Şarkı başarıyla silindi'})
    
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
