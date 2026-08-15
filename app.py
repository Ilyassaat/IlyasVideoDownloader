from flask import Flask, request, jsonify, send_from_directory
import yt_dlp
import os
import uuid

app = Flask(__name__, static_folder=".")

DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


@app.route("/")
def home():
    return send_from_directory(".", "index.html")


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "IlyasVideoDownloader"
    })


@app.route("/api/info", methods=["POST"])
def info():
    try:
        data = request.get_json()
        url = data.get("url", "").strip()

        if not url:
            return jsonify({"error": "Video linki girilmedi."}), 400

        options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
        }

        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)

        formats = []

        for f in info.get("formats", []):
            if not f.get("url"):
                continue

            height = f.get("height")
            ext = f.get("ext")

            if height and ext in ["mp4", "webm"]:
                formats.append({
                    "format_id": f.get("format_id"),
                    "height": height,
                    "ext": ext,
                    "filesize": f.get("filesize") or f.get("filesize_approx"),
                    "fps": f.get("fps"),
                    "url": f.get("url")
                })

        formats.sort(
            key=lambda x: (
                x.get("height") or 0,
                x.get("fps") or 0
            ),
            reverse=True
        )

        return jsonify({
            "success": True,
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "formats": formats[:30]
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
        data = request.get_json()

        url = data.get("url", "").strip()
        format_id = data.get("format_id")

        if not url:
            return jsonify({"error": "Video linki girilmedi."}), 400

        file_id = str(uuid.uuid4())

        output = os.path.join(
            DOWNLOAD_DIR,
            file_id + ".%(ext)s"
        )

        options = {
            "outtmpl": output,
            "quiet": False,
            "noplaylist": True,
        }

        if format_id:
            options["format"] = f"{format_id}+bestaudio/best"
        else:
            options["format"] = "bestvideo+bestaudio/best"

        options["merge_output_format"] = "mp4"

        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)

        filename = None

        for ext in ["mp4", "webm", "mkv"]:
            test = os.path.join(
                DOWNLOAD_DIR,
                file_id + "." + ext
            )

            if os.path.exists(test):
                filename = os.path.basename(test)
                break

        if not filename:
            return jsonify({
                "success": False,
                "error": "Dosya oluşturulamadı."
            }), 500

        return jsonify({
            "success": True,
            "filename": filename,
            "title": info.get("title")
        })

    except Exception as e:
        print("DOWNLOAD HATASI:", str(e))

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/download/<filename>")
def download_file(filename):
    return send_from_directory(
        DOWNLOAD_DIR,
        filename,
        as_attachment=True
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(
        host="0.0.0.0",
        port=port
    )
