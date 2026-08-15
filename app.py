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
    Windows için dosya adını güvenli hale getirir.
    Video başlığını mümkün olduğunca değiştirmez.
    """
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    filename = filename.strip().rstrip(". ")

    if not filename:
        filename = "video"

    return filename


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

        url = data.get("url", "").strip()

        if not url:
            return jsonify({
                "success": False,
                "error": "Video linki girilmedi."
            }), 400

        options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
        }

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

        # Aynı çözünürlükleri mümkün olduğunca tekilleştir
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
            "title": video_info.get("title", "Video"),
            "thumbnail": video_info.get("thumbnail"),
            "duration": video_info.get("duration"),
            "uploader": video_info.get("uploader"),
            "formats": formats
        })

    except Exception as e:
        print("INFO HATASI:", str(e))

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
                "error": "Video linki girilmedi."
            }), 400

        # Önce videonun bilgilerini alıyoruz.
        info_options = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
        }

        with yt_dlp.YoutubeDL(info_options) as ydl:
            video_info = ydl.extract_info(
                url,
                download=False
            )

        title = video_info.get("title") or "video"
        title = clean_filename(title)

        # YouTube başlığı dosya adı olarak kullanılacak.
        output_template = os.path.join(
            DOWNLOAD_DIR,
            title + ".%(ext)s"
        )

        options = {
            "outtmpl": output_template,
            "noplaylist": True,
            "quiet": False,
            "windowsfilenames": True,
            "restrictfilenames": False,
            "overwrites": False,
        }

        # Kullanıcının seçtiği kalite.
        if format_id:
            options["format"] = (
                f"{format_id}+bestaudio/"
                f"{format_id}/bestvideo+bestaudio/best"
            )
        else:
            options["format"] = (
                "bestvideo+bestaudio/"
                "best"
            )

        # Video + ses birleşince MP4.
        options["merge_output_format"] = "mp4"

        print("İNDİRİLİYOR:", title)

        with yt_dlp.YoutubeDL(options) as ydl:
            downloaded_info = ydl.extract_info(
                url,
                download=True
            )

        # Olası dosya isimlerini kontrol et.
        possible_extensions = [
            ".mp4",
            ".webm",
            ".mkv",
            ".mov"
        ]

        final_file = None

        for ext in possible_extensions:
            test_file = os.path.join(
                DOWNLOAD_DIR,
                title + ext
            )

            if os.path.exists(test_file):
                final_file = test_file
                break

        # Dosya bulunamadıysa klasörde başlıkla eşleşen dosyayı ara.
        if not final_file:
            for filename in os.listdir(DOWNLOAD_DIR):

                full_path = os.path.join(
                    DOWNLOAD_DIR,
                    filename
                )

                if not os.path.isfile(full_path):
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
                "error": "İndirilen dosya bulunamadı."
            }), 500

        final_filename = os.path.basename(final_file)

        print("İNDİRME TAMAMLANDI:", final_filename)

        return jsonify({
            "success": True,
            "title": title,
            "filename": final_filename,
            "download_url": "/download/" + final_filename
        })

    except Exception as e:
        print("DOWNLOAD HATASI:", str(e))

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

        for filename in os.listdir(DOWNLOAD_DIR):
            path = os.path.join(
                DOWNLOAD_DIR,
                filename
            )

            if os.path.isfile(path):
                files.append({
                    "filename": filename,
                    "size": os.path.getsize(path)
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
