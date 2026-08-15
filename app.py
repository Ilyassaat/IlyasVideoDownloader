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
    YouTube başlığını mümkün olduğunca aynen korur.
    Sadece Windows'ta yasak olan karakterleri temizler.
    """

    if not filename:
        filename = "video"

    # Windows yasak karakterleri
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)

    # Kontrol karakterlerini temizle
    filename = re.sub(r'[\x00-\x1f\x80-\x9f]', '', filename)

    # Başındaki/sonundaki boşluk ve noktaları temizle
    filename = filename.strip().rstrip(". ")

    # Windows özel isimleri
    reserved = {
        "CON", "PRN", "AUX", "NUL",
        "COM1", "COM2", "COM3", "COM4", "COM5",
        "COM6", "COM7", "COM8", "COM9",
        "LPT1", "LPT2", "LPT3", "LPT4", "LPT5",
        "LPT6", "LPT7", "LPT8", "LPT9"
    }

    if filename.upper() in reserved:
        filename = "_" + filename

    if not filename:
        filename = "video"

    # Windows maksimum yol sorunlarını azalt
    if len(filename) > 180:
        filename = filename[:180].rstrip(". ")

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

        # =========================================================
        # 1. VIDEO BİLGİLERİNİ AL
        # =========================================================

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

        # =========================================================
        # 2. ORİJİNAL YOUTUBE BAŞLIĞINI AL
        # =========================================================

        original_title = video_info.get("title") or "video"

        # Dosya adı için güvenli hale getir
        final_title = clean_filename(original_title)

        print("----------------------------------------")
        print("YOUTUBE BAŞLIĞI :", original_title)
        print("DOSYA ADI       :", final_title)
        print("----------------------------------------")

        # =========================================================
        # 3. GEÇİCİ İNDİRME DOSYASI
        # =========================================================

        temp_template = os.path.join(
            DOWNLOAD_DIR,
            "__ILYAS_TEMP_%(id)s.%(ext)s"
        )

        options = {
            "outtmpl": temp_template,

            "noplaylist": True,

            "quiet": False,

            # Windows karakterlerini yt-dlp'nin değiştirmesine izin verme
            "windowsfilenames": False,

            # Dosya adını kısaltma
            "restrictfilenames": False,

            # Var olan dosyanın üzerine yazma
            "overwrites": False,

            # Video + ses birleşince MP4
            "merge_output_format": "mp4",
        }

        # =========================================================
        # 4. FORMAT
        # =========================================================

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

        # =========================================================
        # 5. İNDİR
        # =========================================================

        print("İNDİRİLİYOR...")

        with yt_dlp.YoutubeDL(options) as ydl:
            downloaded_info = ydl.extract_info(
                url,
                download=True
            )

        print("İNDİRME BİTTİ.")

        # =========================================================
        # 6. GEÇİCİ DOSYAYI BUL
        # =========================================================

        video_id = downloaded_info.get("id")

        possible_files = []

        for filename in os.listdir(DOWNLOAD_DIR):

            if filename.startswith("__ILYAS_TEMP_"):

                full_path = os.path.join(
                    DOWNLOAD_DIR,
                    filename
                )

                if os.path.isfile(full_path):
                    possible_files.append(full_path)

        if not possible_files:
            return jsonify({
                "success": False,
                "error": "İndirilen geçici dosya bulunamadı."
            }), 500

        # En son oluşturulan dosyayı seç
        source_file = max(
            possible_files,
            key=os.path.getmtime
        )

        source_ext = os.path.splitext(
            source_file
        )[1]

        # =========================================================
        # 7. SON DOSYA ADINI OLUŞTUR
        # =========================================================

        # Video + ses birleşmişse MP4
        if source_ext.lower() in [".webm", ".mkv"]:

            # yt-dlp MP4 oluşturduysa MP4 kullan
            mp4_candidate = os.path.splitext(
                source_file
            )[0] + ".mp4"

            if os.path.exists(mp4_candidate):
                source_file = mp4_candidate
                source_ext = ".mp4"

        final_filename = final_title + source_ext.lower()

        final_file = os.path.join(
            DOWNLOAD_DIR,
            final_filename
        )

        # =========================================================
        # 8. DOSYA ADINI ORİJİNAL BAŞLIĞA ÇEVİR
        # =========================================================

        # Aynı isim varsa numara ekle
        # Böylece eski dosyanın üzerine yazılmaz.

        if os.path.exists(final_file):

            base_name = final_title
            extension = source_ext.lower()

            counter = 2

            while True:

                candidate_name = (
                    f"{base_name} ({counter}){extension}"
                )

                candidate_path = os.path.join(
                    DOWNLOAD_DIR,
                    candidate_name
                )

                if not os.path.exists(candidate_path):

                    final_filename = candidate_name
                    final_file = candidate_path

                    break

                counter += 1

        # =========================================================
        # 9. GEÇİCİ DOSYAYI YENİDEN ADLANDIR
        # =========================================================

        os.rename(
            source_file,
            final_file
        )

        print("----------------------------------------")
        print("SON DOSYA :", final_filename)
        print("----------------------------------------")

        return jsonify({
            "success": True,
            "title": original_title,
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
