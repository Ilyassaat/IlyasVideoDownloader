from flask import Flask, request, jsonify, send_from_directory, send_file
import yt_dlp
import os
import uuid
import shutil

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Render/Linux üzerinde sistemde kurulu programları bul
FFMPEG_PATH = shutil.which("ffmpeg")
DENO_PATH = shutil.which("deno")


def base_options():

    options = {
        "quiet": False,
        "no_warnings": False,
        "noplaylist": True,
    }

    # FFmpeg varsa kullan
    if FFMPEG_PATH:
        options["ffmpeg_location"] = FFMPEG_PATH

    # Deno varsa yt-dlp JavaScript runtime olarak kullan
    if DENO_PATH:
        options["js_runtimes"] = {
            "deno": {}
        }

    return options


@app.route("/")
def home():

    return send_from_directory(
        BASE_DIR,
        "index.html"
    )


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

        # ==========================
        # MP3
        # ==========================

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

        # ==========================
        # MP4
        # ==========================

        else:

            if quality == "best":

                video_format = (
                    "bestvideo+bestaudio/"
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

        print("İndirme başlıyor...")

        with yt_dlp.YoutubeDL(options) as ydl:

            info = ydl.extract_info(
                url,
                download=True
            )

        files = os.listdir(
            DOWNLOAD_DIR
        )

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
            "İndirme tamamlandı:",
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

            "error": "Dosya bulunamadı."

        }), 404

    return send_file(
        file_path,
        as_attachment=True
    )


if __name__ == "__main__":

    print("")
    print("====================================")
    print("       ILYAS VIDEO DOWNLOADER")
    print("====================================")

    print("FFmpeg:", FFMPEG_PATH)
    print("Deno:", DENO_PATH)

    print("FFmpeg mevcut:", bool(FFMPEG_PATH))
    print("Deno mevcut:", bool(DENO_PATH))

    print("")

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
