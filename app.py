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
    name = re.sub(r'\s+', ' ', name)
    name = name.strip().rstrip('.')

    if not name:
        name = "video"

    return name


def ytdlp_options():
    return {
        "quiet": True,
        "no_warnings": False,
        "noplaylist": True,

        # YouTube için daha güncel istemci tercihleri
        "extractor_args": {
            "youtube": {
                "player_client": [
                    "web",
                    "mweb"
                ]
            }
        },

        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/151.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    }


@app.route("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/api/health")
def health():
    return jsonify({
        "success": True,
        "service": "Ilyas AI Downloader",
        "status": "online",
        "yt_dlp": yt_dlp.version.__version__
    })


@app.route("/api/info", methods=["POST"])
def info():

    try:
        data = request.get_json(silent=True) or {}
        url = data.get("url", "").strip()

        if not url:
            return jsonify({
                "success": False,
                "error": "YouTube bağlantısı girilmedi."
            }), 400

        options = ytdlp_options()
        options["skip_download"] = True

        with yt_dlp.YoutubeDL(options) as ydl:
            video = ydl.extract_info(
                url,
                download=False
            )

        formats = []

        for fmt in video.get("formats", []):

            height = fmt.get("height")
            width = fmt.get("width")
            ext = fmt.get("ext")

            if not height:
                continue

            if ext not in ["mp4", "webm", "mkv"]:
                continue

            formats.append({
                "format_id": fmt.get("format_id"),
                "height": height,
                "width": width,
                "ext": ext,
                "fps": fmt.get("fps"),
                "filesize": (
                    fmt.get("filesize")
                    or fmt.get("filesize_approx")
                ),
                "has_audio": (
                    fmt.get("acodec") not in [None, "none"]
                )
            })

        # Çözünürlük bazında en iyi seçenekleri seç
        unique = {}

        for fmt in formats:

            height = fmt.get("height")

            if height not in unique:
                unique[height] = fmt
                continue

            current = unique[height]

            if fmt.get("has_audio") and not current.get("has_audio"):
                unique[height] = fmt

        formats = list(unique.values())

        formats.sort(
            key=lambda x: x.get("height") or 0,
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

        error = str(e)

        print("INFO HATASI:", error)

        if "Sign in to confirm" in error:
            message = (
                "YouTube bu sunucu bağlantısını bot olarak algıladı. "
                "Sunucu çalışıyor ancak YouTube erişimi engellendi."
            )
        elif "429" in error:
            message = (
                "YouTube çok fazla istek nedeniyle geçici olarak "
                "erişimi sınırladı."
            )
        else:
            message = error

        return jsonify({
            "success": False,
            "error": message,
            "technical_error": error
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
                "error": "Video bağlantısı girilmedi."
            }), 400

        # Önce bilgileri al
        info_options = ytdlp_options()

        with yt_dlp.YoutubeDL(info_options) as ydl:
            video = ydl.extract_info(
                url,
                download=False
            )

        # ORİJİNAL YOUTUBE BAŞLIĞI
        original_title = video.get("title") or "video"

        # Sadece işletim sistemi için yasak karakterleri temizle
        title = clean_filename(original_title)

        output_template = os.path.join(
            DOWNLOAD_DIR,
            title + ".%(ext)s"
        )

        options = ytdlp_options()

        options.update({
            "outtmpl": output_template,
            "windowsfilenames": True,
            "restrictfilenames": False,
            "overwrites": False,
            "merge_output_format": "mp4",
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

        print("İNDİRİLİYOR:", original_title)

        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([url])

        # Dosyayı bul
        final_file = None

        for filename in os.listdir(DOWNLOAD_DIR):

            full_path = os.path.join(
                DOWNLOAD_DIR,
                filename
            )

            if not os.path.isfile(full_path):
                continue

            name_without_ext = os.path.splitext(
                filename
            )[0]

            if name_without_ext == title:
                final_file = filename
                break

        if not final_file:

            return jsonify({
                "success": False,
                "error": "İndirme tamamlandı ancak dosya bulunamadı."
            }), 500

        print("TAMAMLANDI:", final_file)

        return jsonify({
            "success": True,
            "title": original_title,
            "filename": final_file,
            "download_url": "/download/" + final_file
        })

    except Exception as e:

        error = str(e)

        print("DOWNLOAD HATASI:", error)

        if "Sign in to confirm" in error:
            message = (
                "YouTube sunucu bağlantısını bot olarak engelledi."
            )
        elif "429" in error:
            message = (
                "YouTube geçici olarak istekleri sınırladı."
            )
        else:
            message = error

        return jsonify({
            "success": False,
            "error": message,
            "technical_error": error
        }), 500


@app.route("/download/<path:filename>")
def download_file(filename):

    return send_from_directory(
        DOWNLOAD_DIR,
        filename,
        as_attachment=True
    )


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
