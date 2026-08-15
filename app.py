from flask import Flask, request, jsonify, send_from_directory
import yt_dlp
import os
import re

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def clean_filename(filename):
    """
    YouTube başlığını mümkün olduğunca aynı tutar.
    Sadece işletim sisteminde kullanılamayan karakterleri kaldırır.
    """

    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    filename = filename.strip().rstrip(". ")

    if not filename:
        filename = "video"

    return filename


def ytdlp_base_options():
    """
    Tüm yt-dlp işlemlerinde ortak ayarlar.
    BGUtil POT provider localhost:4416 üzerinden çalışır.
    """

    return {
        "quiet": True,
        "no_warnings": False,
        "noplaylist": True,

        "extractor_args": {
            "youtubepot-bgutilhttp": {
                "base_url": "http://127.0.0.1:4416"
            }
        },

        "js_runtimes": {
            "node": {}
        }
    }


@app.route("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "Ilyas Downloader",
        "yt_dlp": yt_dlp.version.__version__,
        "pot_provider": "bgutil"
    })


@app.route("/api/info", methods=["POST"])
def info():

    try:

        data = request.get_json(silent=True) or {}

        url = data.get("url", "").strip()

        if not url:

            return jsonify({
                "success": False,
                "error": "Video linki girilmedi."
            }), 400

        options = ytdlp_base_options()

        options.update({
            "skip_download": True
        })

        print("BİLGİ ALINIYOR:", url)

        with yt_dlp.YoutubeDL(options) as ydl:

            video_info = ydl.extract_info(
                url,
                download=False
            )

        formats = []

        for fmt in video_info.get("formats", []):

            height = fmt.get("height")
            ext = fmt.get("ext")

            if not height:
                continue

            if ext not in ["mp4", "webm", "mkv"]:
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

                "has_audio": (
                    fmt.get("acodec") not in [None, "none"]
                )
            })

        unique_formats = {}

        for fmt in formats:

            key = (
                fmt["height"],
                fmt["ext"],
                fmt["has_audio"]
            )

            if key not in unique_formats:

                unique_formats[key] = fmt

        formats = list(unique_formats.values())

        formats.sort(
            key=lambda x: (
                x.get("height") or 0,
                x.get("fps") or 0
            ),
            reverse=True
        )

        return jsonify({

            "success": True,

            "title": video_info.get(
                "title",
                "Video"
            ),

            "thumbnail": video_info.get(
                "thumbnail"
            ),

            "duration": video_info.get(
                "duration"
            ),

            "uploader": video_info.get(
                "uploader"
            ),

            "formats": formats
        })

    except Exception as e:

        print(
            "INFO HATASI:",
            repr(e)
        )

        return jsonify({

            "success": False,

            "error": str(e)

        }), 500


@app.route("/api/download", methods=["POST"])
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

                "error": "Video linki girilmedi."

            }), 400

        # -------------------------------------------------
        # 1. VIDEO BILGISI
        # -------------------------------------------------

        info_options = ytdlp_base_options()

        print(
            "VIDEO BILGISI ALINIYOR:",
            url
        )

        with yt_dlp.YoutubeDL(
            info_options
        ) as ydl:

            video_info = ydl.extract_info(
                url,
                download=False
            )

        # -------------------------------------------------
        # 2. VIDEO BASLIGI
        # -------------------------------------------------

        original_title = (
            video_info.get("title")
            or "video"
        )

        title = clean_filename(
            original_title
        )

        print(
            "VIDEO BASLIGI:",
            title
        )

        # -------------------------------------------------
        # 3. DOSYA ADI
        # -------------------------------------------------

        output_template = os.path.join(

            DOWNLOAD_DIR,

            title + ".%(ext)s"
        )

        # -------------------------------------------------
        # 4. DOWNLOAD AYARLARI
        # -------------------------------------------------

        options = ytdlp_base_options()

        options.update({

            "outtmpl": output_template,

            "windowsfilenames": True,

            "restrictfilenames": False,

            "overwrites": False,

            "merge_output_format": "mp4",

            "quiet": False,

            "continuedl": True,

            "retries": 10,

            "fragment_retries": 10
        })

        # -------------------------------------------------
        # 5. FORMAT
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
                "bestvideo+bestaudio/"
                "best"
            )

        # -------------------------------------------------
        # 6. DOWNLOAD
        # -------------------------------------------------

        print(
            "INDIRILIYOR:",
            title
        )

        with yt_dlp.YoutubeDL(
            options
        ) as ydl:

            ydl.extract_info(
                url,
                download=True
            )

        # -------------------------------------------------
        # 7. DOSYAYI BUL
        # -------------------------------------------------

        final_file = None

        possible_extensions = [

            ".mp4",

            ".webm",

            ".mkv",

            ".mov"
        ]

        for ext in possible_extensions:

            test_file = os.path.join(

                DOWNLOAD_DIR,

                title + ext
            )

            if os.path.exists(
                test_file
            ):

                final_file = test_file

                break

        # -------------------------------------------------
        # 8. SON KONTROL
        # -------------------------------------------------

        if not final_file:

            for filename in os.listdir(
                DOWNLOAD_DIR
            ):

                full_path = os.path.join(

                    DOWNLOAD_DIR,

                    filename
                )

                if not os.path.isfile(
                    full_path
                ):

                    continue

                filename_without_ext = os.path.splitext(
                    filename
                )[0]

                if filename_without_ext == title:

                    final_file = full_path

                    break

        if not final_file:

            return jsonify({

                "success": False,

                "error":
                    "İndirilen dosya bulunamadı."
            }), 500

        final_filename = os.path.basename(
            final_file
        )

        print(
            "INDIRME TAMAMLANDI:",
            final_filename
        )

        return jsonify({

            "success": True,

            "title": title,

            "filename": final_filename,

            "download_url":
                "/download/" +
                final_filename
        })

    except Exception as e:

        print(
            "DOWNLOAD HATASI:",
            repr(e)
        )

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

                    "filename": filename,

                    "size":
                        os.path.getsize(path)
                })

        return jsonify({

            "success": True,

            "files": files
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
