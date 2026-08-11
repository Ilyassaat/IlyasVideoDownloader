from flask import Flask, request, jsonify, send_from_directory, send_file
import yt_dlp
import os
import uuid
import glob

app = Flask(__name__)

# =========================================================
# KLASÖRLER
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DOWNLOAD_DIR = os.path.join(
    BASE_DIR,
    "downloads"
)

# bgutil artık /opt/bgutil değil,
# projenin kendi klasöründe olacak.
BGUTIL_SERVER = os.path.join(
    BASE_DIR,
    "bgutil",
    "server"
)

# Render ortamında ffmpeg PATH üzerinden geliyor.
# Bu nedenle Windows'taki ffmpeg klasörünü kullanmıyoruz.
FFMPEG_LOCATION = "ffmpeg"


os.makedirs(
    DOWNLOAD_DIR,
    exist_ok=True
)


# =========================================================
# YT-DLP AYARLARI
# =========================================================

def base_options():

    options = {
        "quiet": False,
        "no_warnings": False,

        "noplaylist": True,

        # YouTube JavaScript challenge
        # Deno yerine Render'daki Node kullanılıyor.
        "js_runtimes": {
            "node": {}
        },

        # YouTube PO Token sağlayıcısı
        "extractor_args": {
            "youtubepot-bgutilscript": {
                "server_home": BGUTIL_SERVER
            }
        },

        # FFmpeg Render sisteminden kullanılacak.
        "ffmpeg_location": FFMPEG_LOCATION,

        # Daha stabil ağ bağlantısı
        "retries": 3,
        "fragment_retries": 3,

        # HTTPS
        "nocheckcertificate": False,
    }

    return options


# =========================================================
# ANA SAYFA
# =========================================================

@app.route("/")
def home():

    return send_from_directory(
        BASE_DIR,
        "index.html"
    )


# =========================================================
# VIDEO BİLGİSİ
# =========================================================

@app.route(
    "/api/info",
    methods=["POST"]
)
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

        with yt_dlp.YoutubeDL(
            options
        ) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )

        formats = info.get(
            "formats",
            []
        )

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

            "duration": info.get(
                "duration"
            ),

            "thumbnail": info.get(
                "thumbnail"
            ),

            "uploader": info.get(
                "uploader"
            ),

            "resolutions": resolutions

        })

    except Exception as e:

        print(
            "INFO HATASI:",
            str(e)
        )

        return jsonify({

            "success": False,

            "error": str(e)

        }), 500


# =========================================================
# VIDEO / MP3 İNDİRME
# =========================================================

@app.route(
    "/api/download",
    methods=["POST"]
)
def download_video():

    data = request.get_json()

    if not data or not data.get("url"):

        return jsonify({

            "success": False,

            "error":
                "Video URL bulunamadı."

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

    file_id = str(
        uuid.uuid4()
    )

    output_template = os.path.join(
        DOWNLOAD_DIR,
        f"{file_id}.%(ext)s"
    )

    try:

        # =================================================
        # MP3
        # =================================================

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

        # =================================================
        # MP4
        # =================================================

        else:

            if quality == "best":

                video_format = (
                    "bestvideo+bestaudio/"
                    "best"
                )

            else:

                try:

                    height = int(
                        quality
                    )

                except ValueError:

                    height = 1080

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

        print("")
        print(
            "======================================"
        )
        print(
            "       ILYAS VIDEO DOWNLOADER"
        )
        print(
            "       İNDİRME BAŞLIYOR"
        )
        print(
            "======================================"
        )
        print(
            "URL:",
            url
        )
        print(
            "TIP:",
            download_type
        )
        print(
            "KALİTE:",
            quality
        )
        print(
            "======================================"
        )

        with yt_dlp.YoutubeDL(
            options
        ) as ydl:

            info = ydl.extract_info(
                url,
                download=True
            )

        # =================================================
        # DOSYAYI BUL
        # =================================================

        files = os.listdir(
            DOWNLOAD_DIR
        )

        matching_files = [

            file

            for file in files

            if file.startswith(
                file_id
            )

        ]

        if not matching_files:

            raise Exception(
                "İndirilen dosya bulunamadı."
            )

        filename = matching_files[0]

        file_path = os.path.join(
            DOWNLOAD_DIR,
            filename
        )

        if not os.path.exists(
            file_path
        ):

            raise Exception(
                "Dosya fiziksel olarak bulunamadı."
            )

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

            "filename":
                filename,

            "download_url":
                "/api/file/" +
                filename

        })

    except Exception as e:

        print("")
        print(
            "DOWNLOAD HATASI:"
        )
        print(
            str(e)
        )
        print("")

        return jsonify({

            "success": False,

            "error":
                str(e)

        }), 500


# =========================================================
# DOSYA SERVİSİ
# =========================================================

@app.route(
    "/api/file/<filename>"
)
def serve_file(filename):

    safe_filename = os.path.basename(
        filename
    )

    file_path = os.path.join(
        DOWNLOAD_DIR,
        safe_filename
    )

    if not os.path.exists(
        file_path
    ):

        return jsonify({

            "success": False,

            "error":
                "Dosya bulunamadı."

        }), 404

    return send_file(
        file_path,
        as_attachment=True
    )


# =========================================================
# SAĞLIK KONTROLÜ
# =========================================================

@app.route("/health")
def health():

    return jsonify({

        "status": "ok",

        "yt_dlp": yt_dlp.version.__version__,

        "ffmpeg":
            "system",

        "node":
            "enabled",

        "bgutil":
            os.path.exists(
                BGUTIL_SERVER
            )

    })


# =========================================================
# LOCAL ÇALIŞTIRMA
# =========================================================

if __name__ == "__main__":

    print("")
    print(
        "===================================="
    )
    print(
        "       ILYAS VIDEO DOWNLOADER"
    )
    print(
        "===================================="
    )

    print(
        "Base:",
        BASE_DIR
    )

    print(
        "Downloads:",
        DOWNLOAD_DIR
    )

    print(
        "BGUTIL:",
        BGUTIL_SERVER
    )

    print(
        "BGUTIL mevcut:",
        os.path.exists(
            BGUTIL_SERVER
        )
    )

    print("")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
