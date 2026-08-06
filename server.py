from flask import Flask, render_template, request, jsonify, send_file
import os
import json
from worker import DownloadWorker

app = Flask(__name__)
worker = DownloadWorker()

# Ana sayfa
@app.route("/")
def index():
    return render_template("index.html")

# Yönetici paneli
@app.route("/admin")
def admin():
    return render_template("admin.html")

# Arama API'si
@app.route("/api/search", methods=["POST"])
def api_search():
    data = request.json
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"status": "error", "message": "Arama terimi gerekli"}), 400
    return jsonify(worker.search(query))

# İndirme API'si
@app.route("/api/download", methods=["POST"])
def api_download():
    data = request.json
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"status": "error", "message": "Video bağlantısı gerekli"}), 400
    result = worker.download_mp3(url)
    return jsonify(result)

# Tüm şarkıları listele
@app.route("/api/songs")
def list_songs():
    songs = []
    if os.path.exists("songs.json"):
        try:
            with open("songs.json", "r", encoding="utf-8") as f:
                songs = json.load(f)
        except:
            pass
    return jsonify(songs)

# MP3 dosyası sunumu
@app.route("/downloads/<filename>")
def serve_file(filename):
    path = os.path.join("downloads", filename)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return "Dosya bulunamadı", 404

if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
