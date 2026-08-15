from flask import Flask, request, jsonify, send_from_directory
import yt_dlp
import os
import re

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# =========================================================
# AYARLAR
# =========================================================

DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")

# Render'da çalışan bgutil POT server
BGUTIL_URL = os.environ.get(
    "BGUTIL_URL",
    "http://127.0.0.1:4416"
)

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


# =========================================================
# DOSYA ADI TEMİZLEME
# =========================================================

def clean_filename(filename):

    if not filename:
        return "video"

    # Windows / Linux için sorun çıkarabilecek karakterler
    filename = re.sub(
        r'[<>:"/\\|?*\x00-\x1f]',
        '',
        filename
    )

    filename = filename.strip()

    # Nokta veya boşlukla bitmesin
    filename = filename.rstrip(". ")

    if not filename:
        return "video"

    # Aşırı uzun dosya adlarını önle
    if len(filename) > 180:
        filename = filename[:180].rstrip()

    return filename


# =========================================================
# YT-DLP TEMEL AYARLARI
# =========================================================

def base_ydl_options():

    return {

        "quiet": True,

        "no_warnings": False,

        "noplaylist": True,

        "nocheckcertificate": True,

        # YouTube POT provider
        "extractor_args": {

            "youtubepot-bgutilhttp": {
                "base_url": BGUTIL_URL
            },

            "youtube": {
                "player_client": [
                    "default",
                    "mweb",
                    "tv"
                ]
            }
        },

        "http_headers": {

            "User-Agent":
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/151.0.0.0 "
                "Safari/537.36",

            "Accept-Language":
                "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
        },

        # Büyük dosyalarda bağlantıyı daha stabil tut
        "http_chunk_size": 10 * 1024 * 1024,

        "retries": 3,

        "fragment_retries": 3,

        "extractor_retries": 3,

        "socket_timeout": 30
    }


# =========================================================
# ANA SAYFA
# =========================================================

@app.route("/")
def home():

    index_path = os.path.join(
        BASE_DIR,
        "index.html"
    )

    if not os.path.exists(index_path):

        return """
        <h1>Ilyas Downloader</h1>
        <p>index.html bulunamadı.</p>
        """, 404

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

        "service":
            "Ilyas Video Downloader",

        "status":
            "online",

        "yt_dlp":
            yt_dlp.version.__version__,

        "bgutil":
            BGUTIL_URL
    })


# =========================================================
# VIDEO BİLGİLERİ
# =========================================================

@app.route(
    "/api/info",
    methods=["POST"]
)
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

                "error":
                    "Video linki girilmedi."

            }), 400


        options = base_ydl_options()

        options["skip_download"] = True


        print("")
        print(
            "========================================"
        )
        print(
            "VIDEO BİLGİSİ ALINIYOR"
        )
        print(
            "URL:",
            url
        )
        print(
            "BGUTIL:",
            BGUTIL_URL
        )
        print(
            "========================================"
        )


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

            width = fmt.get(
                "width"
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


            has_video = (
                fmt.get("vcodec")
                not in [
                    None,
                    "none"
                ]
            )

            has_audio = (
                fmt.get("acodec")
                not in [
                    None,
                    "none"
                ]
            )


            if not has_video:
                continue


            formats.append({

                "format_id":
                    fmt.get(
                        "format_id"
                    ),

                "height":
                    height,

                "width":
                    width,

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
                    has_audio,

                "vcodec":
                    fmt.get(
                        "vcodec"
                    ),

                "acodec":
                    fmt.get(
                        "acodec"
                    )
            })


        # Aynı çözünürlük + format + ses
        # kombinasyonlarını tekilleştir
        unique_formats = {}


        for fmt in formats:

            key = (

                fmt.get(
                    "height"
                ),

                fmt.get(
                    "ext"
                ),

                fmt.get(
                    "has_audio"
                )
            )


            if key not in unique_formats:

                unique_formats[key] = fmt


        formats = list(
            unique_formats.values()
        )


        formats.sort(

            key=lambda x: (

                x.get(
                    "height"
                ) or 0,

                x.get(
                    "fps"
                ) or 0
            ),

            reverse=True
        )


        return jsonify({

            "success":
                True,

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

        error_text = str(e)

        print("")
        print(
            "========================================"
        )
        print(
            "INFO HATASI"
        )
        print(
            error_text
        )
        print(
            "========================================"
        )


        return jsonify({

            "success":
                False,

            "error":
                error_text
        }), 500


# =========================================================
# VİDEO İNDİRME
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

                "success":
                    False,

                "error":
                    "Video linki girilmedi."

            }), 400


        # =================================================
        # ÖNCE VİDEO BİLGİSİ
        # =================================================

        info_options = base_ydl_options()


        with yt_dlp.YoutubeDL(
            info_options
        ) as ydl:

            video_info = ydl.extract_info(
                url,
                download=False
            )


        # =================================================
        # ORİJİNAL YOUTUBE BAŞLIĞI
        # =================================================

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


        print("")
        print(
            "========================================"
        )
        print(
            "İNDİRME BAŞLIYOR"
        )
        print(
            "ORİJİNAL BAŞLIK:",
            original_title
        )
        print(
            "DOSYA ADI:",
            title
        )
        print(
            "FORMAT:",
            format_id
        )
        print(
            "========================================"
        )


        # =================================================
        # DOSYA ÇIKIŞ ŞABLONU
        # =================================================

        output_template = os.path.join(

            DOWNLOAD_DIR,

            title +
            ".%(ext)s"
        )


        # =================================================
        # İNDİRME AYARLARI
        # =================================================

        options = base_ydl_options()


        options.update({

            "outtmpl":
                output_template,

            "windowsfilenames":
                True,

            "restrictfilenames":
                False,

            "overwrites":
                False,

            "continuedl":
                True,

            "merge_output_format":
                "mp4",

            "quiet":
                False
        })


        # =================================================
        # FORMAT
        # =================================================

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


        # =================================================
        # İNDİR
        # =================================================

        with yt_dlp.YoutubeDL(
            options
        ) as ydl:

            ydl.download(
                [url]
            )


        # =================================================
        # DOSYAYI BUL
        # =================================================

        final_file = None


        possible_extensions = [

            ".mp4",

            ".webm",

            ".mkv",

            ".mov"
        ]


        for ext in possible_extensions:

            candidate = os.path.join(

                DOWNLOAD_DIR,

                title + ext
            )


            if os.path.exists(
                candidate
            ):

                final_file = candidate

                break


        # =================================================
        # BAŞKA DOSYA UZANTISI İLE OLUŞMUŞSA
        # =================================================

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


                name_without_ext = (
                    os.path.splitext(
                        filename
                    )[0]
                )


                if (
                    name_without_ext
                    == title
                ):

                    final_file = full_path

                    break


        # =================================================
        # DOSYA BULUNAMADI
        # =================================================

        if not final_file:

            return jsonify({

                "success":
                    False,

                "error":
                    "İndirme tamamlandı ancak dosya bulunamadı."
            }), 500


        final_filename = os.path.basename(
            final_file
        )


        print("")
        print(
            "========================================"
        )
        print(
            "İNDİRME TAMAMLANDI"
        )
        print(
            "DOSYA:",
            final_filename
        )
        print(
            "========================================"
        )


        return jsonify({

            "success":
                True,

            "title":
                title,

            "filename":
                final_filename,

            "download_url":
                "/download/"
                + final_filename
        })


    except Exception as e:

        error_text = str(e)


        print("")
        print(
            "========================================"
        )
        print(
            "DOWNLOAD HATASI"
        )
        print(
            error_text
        )
        print(
            "========================================"
        )


        return jsonify({

            "success":
                False,

            "error":
                error_text
        }), 500


# =========================================================
# DOSYA SERVİSİ
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


            if not os.path.isfile(
                path
            ):

                continue


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
# RENDER
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

        port=port,

        debug=False
    )
