from flask import Flask, request, jsonify, send_from_directory
import yt_dlp
import os
import re
import glob

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def clean_filename(filename):
    # Windows/Linux/Render için güvenli; başlığı mümkün olduğunca aynı tutar.
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', filename)
    filename = filename.strip().rstrip(". ")
    return filename or "video"


def ytdlp_common():
    return {
        "quiet": True,
        "no_warnings": False,
        "noplaylist": True,
        "extractor_args": {
            "youtubepot-bgutilhttp": "base_url=http://127.0.0.1:4416"
        },
    }


@app.route("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "Ilyas Downloader",
        "yt_dlp": yt_dlp.version.__version__
    })


@app.route("/api/info", methods=["POST"])
def info():
    try:
        data = request.get_json(silent=True) or {}
        url = (data.get("url") or "").strip()

        if not url:
            return jsonify({"success": False, "error": "Video linki girilmedi."}), 400

        options = ytdlp_common()
        options.update({
            "skip_download": True,
            "quiet": True,
        })

        with yt_dlp.YoutubeDL(options) as ydl:
            video_info = ydl.extract_info(url, download=False)

        formats = []
        for fmt in video_info.get("formats", []):
            height = fmt.get("height")
            ext = fmt.get("ext")
            if not height or ext not in ("mp4", "webm", "mkv"):
                continue

            formats.append({
                "format_id": fmt.get("format_id"),
                "height": height,
                "width": fmt.get("width"),
                "ext": ext,
                "fps": fmt.get("fps"),
                "filesize": fmt.get("filesize") or fmt.get("filesize_approx"),
                "has_audio": fmt.get("acodec") not in (None, "none")
            })

        # Her çözünürlük için en kullanışlı kaydı tut.
        unique = {}
        for f in formats:
            key = (f["height"], f["ext"], f["has_audio"])
            old = unique.get(key)
            if old is None or (f.get("fps") or 0) > (old.get("fps") or 0):
                unique[key] = f

        formats = sorted(
            unique.values(),
            key=lambda x: (x.get("height") or 0, x.get("fps") or 0),
            reverse=True
        )

        return jsonify({
            "success": True,
            "title": video_info.get("title") or "Video",
            "thumbnail": video_info.get("thumbnail"),
            "duration": video_info.get("duration"),
            "uploader": video_info.get("uploader"),
            "formats": formats
        })

    except Exception as e:
        print("INFO HATASI:", repr(e), flush=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/download", methods=["POST"])
def download():
    try:
        data = request.get_json(silent=True) or {}
        url = (data.get("url") or "").strip()
        format_id = data.get("format_id")

        if not url:
            return jsonify({"success": False, "error": "Video linki girilmedi."}), 400

        # Başlığı indirme başlamadan önce al.
        info_options = ytdlp_common()
        info_options["skip_download"] = True

        with yt_dlp.YoutubeDL(info_options) as ydl:
            video_info = ydl.extract_info(url, download=False)

        title = clean_filename(video_info.get("title") or "video")

        # Aynı başlık varsa yt-dlp dosyayı ezmesin; kullanıcıya karışıklık çıkarmaması
        # için aynı başlık + uzantıyı koruyoruz.
        output_template = os.path.join(DOWNLOAD_DIR, title + ".%(ext)s")

        options = ytdlp_common()
        options.update({
            "outtmpl": output_template,
            "windowsfilenames": True,
            "restrictfilenames": False,
            "overwrites": False,
            "continuedl": True,
            "merge_output_format": "mp4",
            "format": (
                f"{format_id}+bestaudio/bestvideo+bestaudio/best"
                if format_id else
                "bestvideo+bestaudio/best"
            ),
        })

        print("İNDİRİLİYOR:", title, flush=True)

        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.extract_info(url, download=True)

        # Birleştirilmiş son dosyayı bul.
        candidates = []
        for path in glob.glob(os.path.join(DOWNLOAD_DIR, title + ".*")):
            if os.path.isfile(path):
                ext = os.path.splitext(path)[1].lower()
                if ext not in (".part", ".ytdl"):
                    candidates.append(path)

        if not candidates:
            return jsonify({
                "success": False,
                "error": "İndirme tamamlandı ancak dosya bulunamadı."
            }), 500

        # MP4 varsa onu seç.
        final_file = next(
            (p for p in candidates if p.lower().endswith(".mp4")),
            candidates[0]
        )

        final_filename = os.path.basename(final_file)
        print("İNDİRME TAMAMLANDI:", final_filename, flush=True)

        return jsonify({
            "success": True,
            "title": title,
            "filename": final_filename,
            "download_url": "/download/" + final_filename
        })

    except Exception as e:
        print("DOWNLOAD HATASI:", repr(e), flush=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/download/<path:filename>")
def download_file(filename):
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)


@app.route("/api/files")
def list_files():
    try:
        files = []
        for filename in os.listdir(DOWNLOAD_DIR):
            path = os.path.join(DOWNLOAD_DIR, filename)
            if os.path.isfile(path):
                files.append({
                    "filename": filename,
                    "size": os.path.getsize(path)
                })
        return jsonify({"success": True, "files": files})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
