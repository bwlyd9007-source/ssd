from flask import Flask, request, send_file, render_template_string, jsonify
import yt_dlp
import uuid
import os
import threading
import shutil

app = Flask(__name__)

# =========================
# مجلد التحميلات
# =========================
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# =========================
# البحث التلقائي عن FFmpeg
# =========================
FFMPEG_PATH = shutil.which("ffmpeg")

# =========================
# التخزين المؤقت
# =========================
jobs = {}

# =========================
# HTML
# =========================
BASE_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">

<head>

<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>YouTube Downloader Pro</title>

<style>

*{
margin:0;
padding:0;
box-sizing:border-box;
font-family:Arial;
}

body{
background:#0f172a;
color:white;
display:flex;
justify-content:center;
align-items:center;
min-height:100vh;
padding:20px;
}

.container{
width:100%;
max-width:700px;
background:#111827;
padding:25px;
border-radius:20px;
box-shadow:0 0 25px rgba(0,0,0,.4);
}

h1{
text-align:center;
margin-bottom:20px;
}

input,
select,
button{
width:100%;
padding:14px;
border:none;
border-radius:12px;
margin-bottom:15px;
font-size:15px;
}

input,
select{
background:#1f2937;
color:white;
}

button{
background:#22c55e;
color:white;
cursor:pointer;
font-weight:bold;
}

button:hover{
opacity:.9;
}

#status{
text-align:center;
margin-top:10px;
color:#d1d5db;
}

</style>

</head>

<body>

<div class="container">

<h1>🔥 حمزه

<input
id="url"
placeholder="ضع رابط الفيديو هنا"
>

<select id="format">

<option value="mp4">
MP4 فيديو
</option>

<option value="mp3">
MP3 صوت
</option>

</select>

<select id="quality">

<option value="best">
أفضل جودة
</option>

<option value="1080">
1080p
</option>

<option value="720">
720p
</option>

<option value="480">
480p
</option>

<option value="360">
360p
</option>

</select>

<button onclick="startDownload()">
تحميل الآن
</button>

<p id="status">
جاهز
</p>

</div>

<script>

let currentJob = null;

async function startDownload(){

const url = document.getElementById("url").value;

const format = document.getElementById("format").value;

const quality = document.getElementById("quality").value;

if(!url){

alert("ضع رابط الفيديو");

return;

}

document.getElementById("status").innerText =
"جاري التحميل...";

const data = new URLSearchParams();

data.append("url", url);
data.append("format", format);
data.append("quality", quality);

const res = await fetch("/start", {
method:"POST",
body:data
});

const json = await res.json();

currentJob = json.id;

trackDownload();

}

async function trackDownload(){

const res = await fetch("/status/" + currentJob);

const data = await res.json();

document.getElementById("status").innerText =
data.status;

if(data.status === "done"){

const fileRes = await fetch("/file/" + currentJob);

const blob = await fileRes.blob();

const a = document.createElement("a");

a.href = URL.createObjectURL(blob);

a.download = data.name;

a.click();

document.getElementById("status").innerText =
"تم التحميل";

return;

}

setTimeout(trackDownload, 1000);

}

</script>

</body>
</html>
"""

# =========================
# الصفحة الرئيسية
# =========================
@app.route("/")
def home():
    return render_template_string(BASE_HTML)

# =========================
# بدء التحميل
# =========================
@app.route("/start", methods=["POST"])
def start():

    url = request.form.get("url")
    fmt = request.form.get("format")
    quality = request.form.get("quality")

    job_id = str(uuid.uuid4())

    jobs[job_id] = {
        "status": "starting"
    }

    def run():

        try:

            out = os.path.join(
                DOWNLOAD_FOLDER,
                f"{job_id}.%(ext)s"
            )

            # =========================
            # MP4
            # =========================
            if fmt == "mp4":

                if quality == "best":
                    format_code = "bestvideo+bestaudio/best"
                else:
                    format_code = (
                        f"bestvideo[height<={quality}]"
                        f"+bestaudio/best"
                    )

                ydl_opts = {
                    "format": format_code,
                    "outtmpl": out,
                    "ffmpeg_location": FFMPEG_PATH,
                    "merge_output_format": "mp4",
                    "noplaylist": True,
                    "quiet": True
                }

                ext = "mp4"

            # =========================
            # MP3
            # =========================
            else:

                ydl_opts = {
                    "format": "bestaudio/best",
                    "outtmpl": out,
                    "ffmpeg_location": FFMPEG_PATH,
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192"
                    }],
                    "noplaylist": True,
                    "quiet": True
                }

                ext = "mp3"

            # =========================
            # تحميل
            # =========================
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:

                info = ydl.extract_info(
                    url,
                    download=True
                )

                title = info.get("title", "video")

            # =========================
            # البحث عن الملف
            # =========================
            final_file = None

            for f in os.listdir(DOWNLOAD_FOLDER):

                if f.startswith(job_id):

                    if f.endswith(ext):

                        final_file = os.path.join(
                            DOWNLOAD_FOLDER,
                            f
                        )

                        break

            if not final_file:

                jobs[job_id] = {
                    "status": "file not found"
                }

                return

            jobs[job_id] = {
                "status": "done",
                "file": final_file,
                "name": title + "." + ext
            }

        except Exception as e:

            jobs[job_id] = {
                "status": "error: " + str(e)
            }

    threading.Thread(target=run).start()

    return jsonify({
        "id": job_id
    })

# =========================
# الحالة
# =========================
@app.route("/status/<job_id>")
def status(job_id):

    return jsonify(
        jobs.get(job_id, {})
    )

# =========================
# تحميل الملف (مع نافذة اختيار مكان الحفظ)
# =========================
@app.route("/file/<job_id>")
def file(job_id):

    job = jobs[job_id]

    response = send_file(
        job["file"],
        as_attachment=True,
        download_name=job["name"]
    )

    # إجبار المتصفح يفتح نافذة اختيار مكان الحفظ
    response.headers["Content-Disposition"] = f'attachment; filename="{job["name"]}"'

    return response

# =========================
# تشغيل
# =========================
if __name__ == "__main__":

    app.run(
        debug=True,
        host="0.0.0.0",
        port=5000
    )
