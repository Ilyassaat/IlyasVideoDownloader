from flask import Flask, request, jsonify, send_from_directory
import yt_dlp
import os
import re
import glob

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


# =========================================================
# DOSYA ADI
# =========================================================

def clean_filename(filename):
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', filename)
    filename = filename.strip().rstrip(". ")

    if not filename:
        filename = "video"

    return filename


# =========================================================
# YOUTUBE / YT-DLP AYARLARI
# =========================================================

def ytdlp_base_options():

    return {
        "quiet": True,
        "no_warnings": False,

        "noplaylist": True,

        "retries": 5,
        "fragment_retries": 5,

        "socket_timeout": 30,

        # -------------------------------------------------
        # YOUTUBE EJS
        # -------------------------------------------------

        "js_runtimes": {
            "node": {}
        },

        "remote_components": [
            "ejs:github"
        ],

        # -------------------------------------------------
        # BGUTIL POT PROVIDER
        # -------------------------------------------------

        "extractor_args": {

            "youtubepot-bgutilhttp": {
                "base_url": [
                    "http://127.0.0.1:4416"
                ]
            },

            "youtube": {
                "player_client": [
                    "web",
                    "android_vr",
                    "tv_downgraded"
                ]
            }
        }
    }


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
# HEALTH
# =========================================================

@app.route("/api/health")
def health():

    return jsonify({
        "success": True,
        "status": "online",
        "service": "Ilyas Downloader",
        "yt_dlp": yt_dlp.version.__version__
    })


# =========================================================
# VIDEO BİLGİLERİ
# =========================================================

@app.route("/api/info", methods=["POST"])
def info():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        url = data.get(
            "url",
            ""
        ).strip()

        if not url:

            return jsonify({
                "success": False,
                "error": "Video linki girilmedi."
            }), 400


        options = ytdlp_base_options()

        options["skip_download"] = True


        print("")
        print("====================================")
        print("YOUTUBE BILGI ISTEGI")
        print("URL:", url)
        print("====================================")


        with yt_dlp.YoutubeDL(
            options
        ) as ydl:

            video_info = ydl.extract_info(
                url,
                download=False
            )


        formats = []


        for fmt in video_info.get(
            "formats",
            []
        ):

            height = fmt.get(
                "height"
            )

            ext = fmt.get(
                "ext"
            )


            if not height:
                continue


            if ext not in [
                "mp4",
                "webm",
                "mkv"
            ]:
                continue


            formats.append({

                "format_id":
                    fmt.get(
                        "format_id"
                    ),

                "height":
                    height,

                "width":
                    fmt.get(
                        "width"
                    ),

                "ext":
                    ext,

                "fps":
                    fmt.get(
                        "fps"
                    ),

                "filesize":
                    (
                        fmt.get(
                            "filesize"
                        )
                        or
                        fmt.get(
                            "filesize_approx"
                        )
                    ),

                "has_audio":
                    fmt.get(
                        "acodec"
                    ) not in [
                        None,
                        "none"
                    ]
            })


        # Aynı kaliteyi tekilleştir
        unique_formats = {}


        for fmt in formats:

            key = (
                fmt["height"],
                fmt["ext"],
                fmt["has_audio"]
            )


            if key not in unique_formats:

                unique_formats[key] = fmt


        formats = list(
            unique_formats.values()
        )


        formats.sort(
            key=lambda x: (
                x.get("height") or 0,
                x.get("fps") or 0
            ),
            reverse=True
        )


        return jsonify({

            "success": True,

            "title":
                video_info.get(
                    "title",
                    "Video"
                ),

            "thumbnail":
                video_info.get(
                    "thumbnail"
                ),

            "duration":
                video_info.get(
                    "duration"
                ),

            "uploader":
                video_info.get(
                    "uploader"
                ),

            "formats":
                formats
        })


    except Exception as e:

        print("")
        print("====================================")
        print("INFO HATASI")
        print(repr(e))
        print("====================================")


        return jsonify({

            "success": False,

            "error":
                str(e)

        }), 500


# =========================================================
# DOWNLOAD
# =========================================================

@app.route(
    "/api/download",
    methods=["POST"]
)
def download():

    try:

        data = request.get_json(
            silent=True
        ) or {}


        url = data.get(
            "url",
            ""
        ).strip()


        format_id = data.get(
            "format_id"
        )


        if not url:

            return jsonify({

                "success": False,

                "error":
                    "Video linki girilmedi."

            }), 400


        # -------------------------------------------------
        # VIDEO BILGISI
        # -------------------------------------------------

        info_options = (
            ytdlp_base_options()
        )

        info_options[
            "skip_download"
        ] = True


        print("")
        print("====================================")
        print("VIDEO BILGISI ALINIYOR")
        print("====================================")


        with yt_dlp.YoutubeDL(
            info_options
        ) as ydl:

            video_info = ydl.extract_info(
                url,
                download=False
            )


        original_title = (
            video_info.get(
                "title"
            )
            or
            "video"
        )


        title = clean_filename(
            original_title
        )


        # -------------------------------------------------
        # DOSYA ADI
        # -------------------------------------------------

        output_template = os.path.join(

            DOWNLOAD_DIR,

            title + ".%(ext)s"

        )


        options = (
            ytdlp_base_options()
        )


        options.update({

            "outtmpl":
                output_template,

            "overwrites":
                False,

            "windowsfilenames":
                True,

            "restrictfilenames":
                False,

            "merge_output_format":
                "mp4",

            "quiet":
                False
        })


        # -------------------------------------------------
        # FORMAT
        # -------------------------------------------------

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


        print("")
        print("====================================")
        print("INDIRME BASLIYOR")
        print("BASLIK:", original_title)
        print("DOSYA:", title)
        print("FORMAT:", format_id)
        print("====================================")


        # -------------------------------------------------
        # DOWNLOAD
        # -------------------------------------------------

        with yt_dlp.YoutubeDL(
            options
        ) as ydl:

            ydl.extract_info(
                url,
                download=True
            )


        # -------------------------------------------------
        # DOSYAYI BUL
        # -------------------------------------------------

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


            if os.path.isfile(
                candidate
            ):

                final_file = candidate

                break


        # -------------------------------------------------
        # FALLBACK
        # -------------------------------------------------

        if not final_file:

            candidates = glob.glob(

                os.path.join(
                    DOWNLOAD_DIR,
                    title + ".*"
                )

            )


            candidates = [

                x for x in candidates

                if os.path.isfile(x)

                and not x.endswith(".part")

                and not x.endswith(".ytdl")

            ]


            if candidates:

                final_file = candidates[0]


        # -------------------------------------------------
        # DOSYA YOK
        # -------------------------------------------------

        if not final_file:

            return jsonify({

                "success": False,

                "error":
                    "İndirilen dosya bulunamadı."

            }), 500


        final_filename = os.path.basename(
            final_file
        )


        print("")
        print("====================================")
        print("INDIRME TAMAMLANDI")
        print(final_filename)
        print("====================================")


        return jsonify({

            "success": True,

            "title":
                original_title,

            "filename":
                final_filename,

            "download_url":
                "/download/" +
                final_filename

        })


    except Exception as e:

        print("")
        print("====================================")
        print("DOWNLOAD HATASI")
        print(repr(e))
        print("====================================")


        return jsonify({

            "success": False,

            "error":
                str(e)

        }), 500


# =========================================================
# DOSYA INDIR
# =========================================================

@app.route(
    "/download/<path:filename>"
)
def download_file(filename):

    return send_from_directory(

        DOWNLOAD_DIR,

        filename,

        as_attachment=True

    )


# =========================================================
# DOSYALAR
# =========================================================

@app.route("/api/files")
def list_files():

    try:

        files = []


        for filename in os.listdir(
            DOWNLOAD_DIR
        ):

            path = os.path.join(
                DOWNLOAD_DIR,
                filename
            )


            if os.path.isfile(path):

                files.append({

                    "filename":
                        filename,

                    "size":
                        os.path.getsize(
                            path
                        )

                })


        return jsonify({

            "success":
                True,

            "files":
                files

        })


    except Exception as e:

        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 500


# =========================================================
# DEBUG
# =========================================================

@app.route("/api/debug")
def debug():

    import subprocess

    result = {}

    try:

        p = subprocess.run(

            [
                "yt-dlp",
                "--version"
            ],

            capture_output=True,
            text=True,
            timeout=20

        )

        result["yt_dlp"] = (
            p.stdout.strip()
        )

    except Exception as e:

        result["yt_dlp"] = str(e)


    try:

        p = subprocess.run(

            [
                "node",
                "--version"
            ],

            capture_output=True,
            text=True,
            timeout=10

        )

        result["node"] = (
            p.stdout.strip()
        )

    except Exception as e:

        result["node"] = str(e)


    try:

        p = subprocess.run(

            [
                "yt-dlp",
                "-v",
                "--simulate",
                "--js-runtimes",
                "node",
                "--remote-components",
                "ejs:github",
                "--extractor-args",
                "youtubepot-bgutilhttp:base_url=http://127.0.0.1:4416",
                "https://www.youtube.com/watch?v=BvwQJlvO_1Y"
            ],

            capture_output=True,
            text=True,
            timeout=90

        )


        output = (
            p.stdout +
            "\n" +
            p.stderr
        )


        result["youtube_debug"] = [

            line

            for line in output.splitlines()

            if (
                "PO Token Providers" in line
                or
                "Plugin directories" in line
                or
                "JS runtimes" in line
                or
                "[jsc]" in line
                or
                "[pot]" in line
            )

        ]


    except Exception as e:

        result["youtube_debug"] = [
            str(e)
        ]


    return jsonify(result)


# =========================================================
# START
# =========================================================

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
