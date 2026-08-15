from flask import Flask, request, jsonify, send_from_directory
import yt_dlp
import os
import re

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def clean_filename(name):
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = name.strip().rstrip(". ")

    return name or "video"


@app.route("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/api/health")
def health():
    return jsonify({
        "success": True,
        "status": "online",
        "service": "Ilyas Downloader",
        "yt_dlp": yt_dlp.version.__version__
    })


def get_ydl_options():
    return {
        "quiet": True,
        "no_warnings": False,
        "noplaylist": True,

        # YouTube istemci ayarları
        "extractor_args": {
            "youtube": {
                "player_client": ["android_vr", "web"]
            }
        },

        # Daha stabil bağlantı
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
    }


@app.route("/api/info", methods=["POST"])
def info():
    try:
        data = request.get_json(silent=True) or {}
        url = data.get("url", "").strip()

        if not url:
            return jsonify({
                "success": False,
                "error": "YouTube linki girilmedi."
            }), 400

        options = get_ydl_options()
        options["skip_download"] = True

        with yt_dlp.YoutubeDL(options) as ydl:
            video = ydl.extract_info(url, download=False)

        formats = []

        for fmt in video.get("formats", []):
            height = fmt.get("height")
            ext = fmt.get("ext")

            if not height:
                continue

            if ext not in ("mp4", "webm", "mkv"):
                continue

            formats.append({
                "format_id": fmt.get("format_id"),
                "height": height,
                "width": fmt.get("width"),
                "ext": ext,
                "fps": fmt.get("fps"),
                "filesize": (
                    fmt.get("filesize")
                    or fmt.get("filesize_approx")
                ),
                "has_audio": fmt.get("acodec") not in (
                    None,
                    "none"
                )
            })

        # Aynı kaliteyi tekrar göstermemek için
        unique = {}

        for fmt in formats:
            key = (
                fmt["height"],
                fmt["ext"],
                fmt["has_audio"]
            )

            if key not in unique:
                unique[key] = fmt

        formats = list(unique.values())

        formats.sort(
            key=lambda x: (
                x.get("height") or 0,
                x.get("fps") or 0
            ),
            reverse=True
        )

        return jsonify({
            "success": True,
            "title": video.get("title") or "Video",
            "thumbnail": video.get("thumbnail"),
            "duration": video.get("duration"),
            "uploader": video.get("uploader"),
            "formats": formats
        })

    except Exception as e:
        print("INFO HATASI:", repr(e))

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/download", methods=["POST"])
def download():
    try:
        data = request.get_json(silent=True) or {}

        url = data.get("url", "").strip()
        format_id = data.get("format_id")

        if not url:
            return jsonify({
                "success": False,
                "error": "YouTube linki girilmedi."
            }), 400

        # Videonun GERÇEK başlığını al
        info_options = get_ydl_options()
        info_options["skip_download"] = True

        with yt_dlp.YoutubeDL(info_options) as ydl:
            video_info = ydl.extract_info(
                url,
                download=False
            )

        original_title = video_info.get("title") or "video"
        title = clean_filename(original_title)

        # DOSYA ADI VİDEONUN BAŞLIĞI OLACAK
        output_template = os.path.join(
            DOWNLOAD_DIR,
            f"{title}.%(ext)s"
        )

        options = get_ydl_options()

        options.update({
            "outtmpl": output_template,

            # Mevcut dosyayı ezme
            "overwrites": False,

            # Windows benzeri güvenli isim
            "windowsfilenames": True,

            # Dosya adını kısaltma
            "restrictfilenames": False,

            # MP4 tercih et
            "merge_output_format": "mp4",

            # İndirme
            "quiet": False,

            "retries": 5,
            "fragment_retries": 5,
        })

        if format_id:
            options["format"] = (
                f"{format_id}+bestaudio/"
                f"{format_id}/"
                f"bestvideo+bestaudio/"
                f"best"
            )
        else:
            options["format"] = (
                "bestvideo+bestaudio/best"
            )

        print("--------------------------------")
        print("VIDEO:", original_title)
        print("DOSYA:", title)
        print("FORMAT:", format_id)
        print("--------------------------------")

        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.extract_info(
                url,
                download=True
            )

        # İndirilmiş dosyayı bul
        final_file = None

        extensions = [
            ".mp4",
            ".webm",
            ".mkv",
            ".mov"
        ]

        for ext in extensions:
            candidate = os.path.join(
                DOWNLOAD_DIR,
                title + ext
            )

            if os.path.isfile(candidate):
                final_file = candidate
                break

        # Eğer birleşme farklı isimle olduysa
        if final_file is None:

            candidates = []

            for filename in os.listdir(DOWNLOAD_DIR):

                path = os.path.join(
                    DOWNLOAD_DIR,
                    filename
                )

                if not os.path.isfile(path):
                    continue

                base = os.path.splitext(filename)[0]

                if base == title:
                    candidates.append(path)

            if candidates:
                final_file = candidates[0]

        if final_file is None:
            return jsonify({
                "success": False,
                "error": "İndirilen dosya bulunamadı."
            }), 500

        filename = os.path.basename(final_file)

        print("TAMAMLANDI:", filename)

        return jsonify({
            "success": True,
            "title": original_title,
            "filename": filename,
            "download_url": "/download/" + filename
        })

    except Exception as e:
        print("DOWNLOAD HATASI:", repr(e))

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/download/<path:filename>")
def download_file(filename):
    return send_from_directory(
        DOWNLOAD_DIR,
        filename,
        as_attachment=True
    )


@app.route("/api/files")
def files():
    try:
        result = []

        for filename in os.listdir(DOWNLOAD_DIR):

            path = os.path.join(
                DOWNLOAD_DIR,
                filename
            )

            if os.path.isfile(path):
                result.append({
                    "filename": filename,
                    "size": os.path.getsize(path),
                    "download_url": "/download/" + filename
                })

        return jsonify({
            "success": True,
            "files": result
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
