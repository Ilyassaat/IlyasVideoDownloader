from flask import Flask, request, jsonify, send_from_directory, send_file
import yt_dlp
import os
import uuid

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def base_options():
    return {
        "quiet": False,
        "no_warnings": False,
        "noplaylist": True,

        # Render üzerinde bulunan Node.js kullanılır
        "js_runtimes": {
            "node": {}
        },

        # BGUTIL PO Token sağlayıcısı
        "extractor_args": {
            "youtube": {
                "player_client": [
                    "mweb",
                    "web_safari",
                    "tv"
                ]
            },
            "youtubepot-bgutilhttp": {
                "base_url": "http://127.0.0.1:4416"
            }
        },

        # Daha stabil bağlantı
        "retries": 5,
        "fragment_retries": 5,
        "socket_timeout": 30,

        # IPv4 kullan
        "source_address": "0.0.0.0",

        # User-Agent
        "http_headers": {
            "User-Agent":
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/151.0.0.0 Safari/537.36"
        }
    }


@app.route("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/api/info", methods=["POST"])
def video_info():

    data = request.get_json()

    if not data or not data.get("url"):
        return jsonify({
            "success": False,
            "error": "Video URL bulunamadı."
        }), 400

    url = data["url"].strip()

    try:

        options = base_options()
        options["skip_download"] = True

        with yt_dlp.YoutubeDL(options) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )

        formats = info.get("formats", [])

        resolutions = set()

        for fmt in formats:

            height = fmt.get("height")

            if not height:
                continue

            if height >= 2160:
                resolutions.add(2160)

            elif height >= 1440:
                resolutions.add(1440)

            elif height >= 1080:
                resolutions.add(1080)

            elif height >= 720:
                resolutions.add(720)

            elif height >= 480:
                resolutions.add(480)

            elif height >= 360:
                resolutions.add(360)

        resolutions = sorted(
            resolutions,
            reverse=True
        )

        return jsonify({

            "success": True,

            "title": info.get(
                "title",
                "Bilinmeyen video"
            ),

            "duration": info.get("duration"),

            "thumbnail": info.get("thumbnail"),

            "uploader": info.get("uploader"),

            "resolutions": resolutions

        })

    except Exception as e:

        print("INFO HATASI:", str(e))

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/download", methods=["POST"])
def download_video():

    data = request.get_json()

    if not data or not data.get("url"):

        return jsonify({
            "success": False,
            "error": "Video URL bulunamadı."
        }), 400

    url = data["url"].strip()

    download_type = data.get(
        "type",
        "video"
    )

    quality = data.get(
        "quality",
        "best"
    )

    audio_quality = data.get(
        "audio_quality",
        "192"
    )

    file_id = str(uuid.uuid4())

    output_template = os.path.join(
        DOWNLOAD_DIR,
        f"{file_id}.%(ext)s"
    )

    try:

        # =========================
        # MP3
        # =========================

        if download_type == "audio":

            options = base_options()

            options.update({

                "format":
                    "bestaudio/best",

                "outtmpl":
                    output_template,

                "postprocessors": [
                    {
                        "key":
                            "FFmpegExtractAudio",

                        "preferredcodec":
                            "mp3",

                        "preferredquality":
                            str(audio_quality)
                    }
                ]

            })

        # =========================
        # MP4
        # =========================

        else:

            if quality == "best":

                video_format = (
                    "bestvideo*+bestaudio/"
                    "best"
                )

            else:

                height = int(quality)

                video_format = (
                    f"bestvideo[height<={height}]"
                    "+bestaudio/"
                    f"best[height<={height}]"
                )

            options = base_options()

            options.update({

                "format":
                    video_format,

                "outtmpl":
                    output_template,

                "merge_output_format":
                    "mp4"

            })

        print("====================================")
        print("İNDİRME BAŞLIYOR")
        print("URL:", url)
        print("TYPE:", download_type)
        print("QUALITY:", quality)
        print("====================================")

        with yt_dlp.YoutubeDL(options) as ydl:

            info = ydl.extract_info(
                url,
                download=True
            )

        files = os.listdir(DOWNLOAD_DIR)

        matching_files = [
            file
            for file in files
            if file.startswith(file_id)
        ]

        if not matching_files:

            raise Exception(
                "İndirilen dosya bulunamadı."
            )

        filename = matching_files[0]

        print(
            "İNDİRME TAMAMLANDI:",
            filename
        )

        return jsonify({

            "success": True,

            "title": info.get(
                "title",
                "Video"
            ),

            "filename": filename,

            "download_url":
                "/api/file/" + filename

        })

    except Exception as e:

        print(
            "DOWNLOAD HATASI:",
            str(e)
        )

        return jsonify({

            "success": False,

            "error": str(e)

        }), 500


@app.route("/api/file/<filename>")
def serve_file(filename):

    safe_filename = os.path.basename(
        filename
    )

    file_path = os.path.join(
        DOWNLOAD_DIR,
        safe_filename
    )

    if not os.path.exists(file_path):

        return jsonify({

            "success": False,

            "error":
                "Dosya bulunamadı."

        }), 404

    return send_file(
        file_path,
        as_attachment=True
    )


@app.route("/api/status")
def status():

    return jsonify({

        "service":
            "Ilyas Downloader",

        "status":
            "ok",

        "yt_dlp":
            yt_dlp.version.__version__,

        "bgutil":
            "enabled",

        "node":
            "enabled"

    })


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        )
    )
