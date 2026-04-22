#!/usr/bin/env python3
"""
PackTrack — single-file web app.

Run:   python app.py
Open:  http://localhost:5001

Pages:
  /         Search your inventory
  /labels   Generate & print QR code box labels
  /upload   Process a packing video (optional, or use CLI: process.py)
"""

import base64
import io
import os
import re
import sqlite3
import subprocess
import threading
from pathlib import Path

from flask import (Flask, abort, redirect, render_template_string, request,
                   send_file, url_for)

try:
    import qrcode
    from PIL import Image
except ImportError:
    raise SystemExit("Missing deps. Run: pip install -r requirements.txt")

DB_PATH = Path("packtrack.db")
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024 * 1024   # 8 GB upload cap


# ---------------------------------------------------------------------------
# Shared HTML chrome
# ---------------------------------------------------------------------------

_BASE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PackTrack — {{ page_title }}</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, -apple-system, sans-serif;
         background: #111; color: #ddd; min-height: 100vh; }
  .wrap { max-width: 1100px; margin: 0 auto; padding: 24px 20px; }

  header { display: flex; align-items: center; justify-content: space-between;
           margin-bottom: 28px; padding-bottom: 16px; border-bottom: 1px solid #2a2a2a; }
  header h1 { font-size: 1.6rem; color: #4af; }
  header h1 small { font-size: 0.82rem; color: #666; font-weight: normal; margin-left: 8px; }
  nav a { color: #89c; text-decoration: none; margin-left: 18px; font-size: 0.95rem; }
  nav a:hover { color: #4af; }
  nav a.active { color: #4af; font-weight: 600; }

  h2 { color: #eee; margin-bottom: 14px; font-size: 1.2rem; }
  form.row { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
  input[type=text], input[type=number], select, input[type=file] {
    padding: 10px 14px; font-size: 0.96rem; background: #222;
    border: 1px solid #444; color: #eee; border-radius: 8px; outline: none;
  }
  input[type=text] { flex: 1; min-width: 200px; }
  input:focus, select:focus { border-color: #4af; }
  label { display: flex; flex-direction: column; gap: 4px; font-size: 0.82rem; color: #888; }
  button, .btn { padding: 10px 20px; background: #4af; color: #000;
                 font-weight: 700; font-size: 0.96rem; border: none;
                 border-radius: 8px; cursor: pointer; white-space: nowrap;
                 text-decoration: none; display: inline-block; }
  button:hover, .btn:hover { background: #6cf; }
  .btn-secondary { background: #333; color: #eee; }
  .btn-secondary:hover { background: #444; }

  .card { background: #1c1c1c; border: 1px solid #2a2a2a; border-radius: 10px;
          padding: 18px; margin-bottom: 16px; }

  .tip { background: #1a2030; border: 1px solid #2a3a55; border-radius: 8px;
         padding: 14px 18px; font-size: 0.9rem; color: #89a; margin-bottom: 24px; }
  .tip strong { color: #acd; }

  .empty { text-align: center; padding: 60px 20px; color: #555; font-size: 1.05rem; }

  @media print {
    body { background: white; color: black; }
    .no-print { display: none !important; }
    .wrap { max-width: 100%; padding: 0; }
  }
</style>
</head>
<body>
<div class="wrap">
  <header class="no-print">
    <h1>📦 PackTrack <small>moving inventory</small></h1>
    <nav>
      <a href="{{ url_for('index') }}"  class="{{ 'active' if page=='search'  else '' }}">Search</a>
      <a href="{{ url_for('labels') }}" class="{{ 'active' if page=='labels'  else '' }}">Labels</a>
      <a href="{{ url_for('upload') }}" class="{{ 'active' if page=='upload'  else '' }}">Process Video</a>
    </nav>
  </header>
  {{ body | safe }}
</div>
</body>
</html>"""


def render(body_html: str, *, page: str, title: str, **ctx):
    rendered_body = render_template_string(body_html, **ctx)
    return render_template_string(_BASE, body=rendered_body, page=page, page_title=title)


# ---------------------------------------------------------------------------
# /  — Search
# ---------------------------------------------------------------------------

_SEARCH_BODY = """
<form class="row no-print" method="get" action="/">
  <input type="text" name="q" value="{{ query|e }}"
         placeholder="Search: HDMI cables, soldering iron, kitchen stuff…" autofocus>
  <button type="submit">Find It</button>
</form>

{% if not query %}
<div class="tip no-print">
  💡 <strong>Start here:</strong>
  <a href="{{ url_for('labels') }}" style="color:#4af">Generate QR labels</a>
  to print and stick on your boxes — then process a video on the
  <a href="{{ url_for('upload') }}" style="color:#4af">Process Video</a> page.
  Come back here to find anything later.
</div>
{% endif %}

{% if query %}
  {% if results %}
    <div style="color:#666; font-size: 0.9rem; margin-bottom: 14px;">
      {{ results|length }} result(s) for "<strong>{{ query|e }}</strong>"
    </div>
    {% for r in results %}
    <div class="card">
      <div style="font-size:1.25rem; font-weight:700; color:#4af; margin-bottom:4px;">
        📦 {{ r.box_label or "Unknown Box" }}
      </div>
      <div style="color:#666; font-size:0.82rem; margin-bottom:10px;">
        {{ r.video_name }} &middot; {{ r.time_fmt }}
      </div>
      {% if r.narration %}
      <div style="color:#888; font-size:0.75rem; text-transform:uppercase; letter-spacing:0.05em;">You said</div>
      <div style="margin:2px 0 10px; color:#ccc;">{{ r.narration }}</div>
      {% endif %}
      <div style="color:#888; font-size:0.75rem; text-transform:uppercase; letter-spacing:0.05em;">Camera saw</div>
      <div style="margin:2px 0 10px; color:#aaa; font-style:italic;">{{ r.visual_description }}</div>
      {% if r.frame_path %}
      <img src="/frame/{{ r.frame_path }}" style="max-height:220px; border-radius:6px;">
      {% endif %}
    </div>
    {% endfor %}
  {% else %}
    <div class="empty">Nothing found for "<strong>{{ query|e }}</strong>"</div>
  {% endif %}
{% endif %}
"""


def _safe_fts(raw: str) -> str:
    return re.sub(r'[^\w\s]', ' ', raw).strip()


@app.route("/")
def index():
    query = request.args.get("q", "").strip()
    results = []

    if query and DB_PATH.exists():
        safe_q = _safe_fts(query)
        if safe_q:
            conn = sqlite3.connect(DB_PATH)
            try:
                rows = conn.execute(
                    """SELECT pe.box_label, pe.narration, pe.visual_description,
                              pe.frame_path, pe.timestamp, s.video_file
                       FROM search_fts sf
                       JOIN packing_events pe ON sf.event_id = pe.id
                       JOIN sessions s ON pe.session_id = s.id
                       WHERE search_fts MATCH ?
                       ORDER BY rank LIMIT 40""",
                    (safe_q,),
                ).fetchall()
            except Exception:
                rows = []
            conn.close()
            for box, narr, visual, frame, ts, vid in rows:
                mins, secs = divmod(int(ts or 0), 60)
                results.append({
                    "box_label": box,
                    "narration": (narr or "")[:220],
                    "visual_description": (visual or "")[:220],
                    "frame_path": frame,
                    "time_fmt": f"{mins}:{secs:02d}",
                    "video_name": Path(vid).name if vid else "",
                })

    return render(_SEARCH_BODY, page="search", title="Search",
                  query=query, results=results)


@app.route("/frame/<path:frame_path>")
def serve_frame(frame_path):
    p = Path(frame_path)
    if not p.exists() or p.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        abort(404)
    return send_file(p)


# ---------------------------------------------------------------------------
# /labels  — QR code label sheet (print-friendly)
# ---------------------------------------------------------------------------

_LABELS_BODY = """
<h2 class="no-print">QR Code Box Labels</h2>

<form class="row no-print" method="get" action="/labels">
  <label>Prefix <input type="text"   name="prefix" value="{{ prefix|e }}" size="6"></label>
  <label>From   <input type="number" name="start"  value="{{ start }}" min="1" max="9999" style="width:80px"></label>
  <label>To     <input type="number" name="end"    value="{{ end }}"   min="1" max="9999" style="width:80px"></label>
  <label>Per row
    <select name="cols">
      {% for n in [2,3,4] %}<option value="{{n}}" {% if cols==n %}selected{% endif %}>{{n}}</option>{% endfor %}
    </select>
  </label>
  <label>Size
    <select name="size">
      <option value="small"  {% if size=='small'  %}selected{% endif %}>Small</option>
      <option value="medium" {% if size=='medium' %}selected{% endif %}>Medium</option>
      <option value="large"  {% if size=='large'  %}selected{% endif %}>Large</option>
    </select>
  </label>
  <button type="submit">Generate</button>
  <button type="button" onclick="window.print()" class="btn-secondary">🖨️ Print</button>
</form>

{% if labels %}
<div class="tip no-print">
  <strong>Print tips:</strong> Use Ctrl+P → set margins to "Minimum" and scale to 100%.
  Tape to boxes with the QR clearly visible. The camera reads
  <code style="background:#333;padding:2px 6px;border-radius:3px">PACKTRACK:{{ prefix }}-N</code>
  codes automatically.
</div>

<div style="display: grid; grid-template-columns: repeat({{ cols }}, 1fr);
            gap: {{ gap }}px; margin-top: 8px;">
  {% for lbl in labels %}
  <div style="background: white; color: black; border: 1px solid #ccc;
              border-radius: 6px; padding: {{ pad }}px; text-align: center;
              page-break-inside: avoid; break-inside: avoid;">
    <img src="data:image/png;base64,{{ lbl.png }}"
         style="width: 100%; max-width: {{ qr_px }}px; height: auto; display: block; margin: 0 auto;">
    <div style="font-family: monospace; font-weight: 700; font-size: {{ font_size }}px;
                margin-top: 6px; letter-spacing: 0.02em;">{{ lbl.id }}</div>
  </div>
  {% endfor %}
</div>
{% else %}
<div class="empty">Set a range above and click Generate.</div>
{% endif %}
"""


def _qr_png_b64(box_id: str) -> str:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(f"PACKTRACK:{box_id}")
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


_SIZE_TABLE = {
    "small":  {"qr_px": 150, "pad":  8, "gap":  8, "font_size": 16},
    "medium": {"qr_px": 220, "pad": 12, "gap": 14, "font_size": 22},
    "large":  {"qr_px": 320, "pad": 16, "gap": 20, "font_size": 30},
}


@app.route("/labels")
def labels():
    prefix = (request.args.get("prefix") or "BOX").strip().upper()
    start  = max(1, int(request.args.get("start") or 1))
    end    = min(9999, int(request.args.get("end") or 0))
    cols   = int(request.args.get("cols")  or 3)
    size   = request.args.get("size") or "medium"
    if size not in _SIZE_TABLE:
        size = "medium"

    # Only generate on explicit request (has ?start= in query)
    has_query = "start" in request.args or "end" in request.args
    labels_data = []
    if has_query and end >= start and (end - start) < 300:
        for n in range(start, end + 1):
            box_id = f"{prefix}-{n}"
            labels_data.append({"id": box_id, "png": _qr_png_b64(box_id)})

    dims = _SIZE_TABLE[size]
    return render(_LABELS_BODY, page="labels", title="Labels",
                  prefix=prefix, start=start, end=end or 20,
                  cols=cols, size=size, labels=labels_data, **dims)


# ---------------------------------------------------------------------------
# /upload  — Process a video file
# ---------------------------------------------------------------------------

_UPLOAD_BODY = """
<h2 class="no-print">Process a Packing Video</h2>

{% if not api_key_set %}
<div class="tip" style="background:#301a1a; border-color:#552a2a; color:#eab;">
  ⚠️ <strong>OPENAI_API_KEY not set.</strong> Set it before running this app:<br>
  <code style="background:#222; padding:4px 10px; border-radius:4px; display:inline-block; margin-top:6px;">
    $env:OPENAI_API_KEY = "sk-..."   (PowerShell)
  </code>
</div>
{% endif %}

{% if not ffmpeg_ok %}
<div class="tip" style="background:#301a1a; border-color:#552a2a; color:#eab;">
  ⚠️ <strong>ffmpeg not found on PATH.</strong>
  Install it from <a href="https://ffmpeg.org/download.html" style="color:#fca">ffmpeg.org</a>
  (or on Windows: <code>winget install ffmpeg</code>)
</div>
{% endif %}

{% if job_status %}
<div class="card">
  <h2>Current Job</h2>
  <div style="color:#ccc; margin: 6px 0;">Video: <strong>{{ job_status.video }}</strong></div>
  <div style="color:#ccc; margin: 6px 0;">Status: <strong>{{ job_status.state }}</strong></div>
  <pre style="background:#0d0d0d; padding: 12px; border-radius: 6px; overflow: auto; max-height: 400px; color:#9c9; font-size: 0.82rem; white-space: pre-wrap;">{{ job_status.log }}</pre>
  {% if job_status.state == 'running' %}
  <div class="tip">Refreshing every 3 seconds…</div>
  <script>setTimeout(() => location.reload(), 3000);</script>
  {% endif %}
</div>
{% endif %}

<div class="card">
  <h2>Upload Video</h2>
  <form method="post" action="/upload" enctype="multipart/form-data">
    <div style="margin-bottom: 12px;">
      <label>Video file (MP4, MOV, etc.)
        <input type="file" name="video" accept="video/*" required>
      </label>
    </div>
    <div style="margin-bottom: 12px;">
      <label>Frame interval (seconds between frames — lower = more detail, higher cost)
        <input type="number" name="interval" value="30" min="5" max="120" style="width:100px">
      </label>
    </div>
    <button type="submit" {% if not api_key_set or not ffmpeg_ok %}disabled style="opacity:0.5; cursor:not-allowed"{% endif %}>
      Start Processing
    </button>
  </form>
</div>

<div class="card">
  <h2>Or use the CLI</h2>
  <pre style="background:#0d0d0d; padding: 12px; border-radius: 6px; color:#bcb; font-size: 0.88rem;">python process.py process path\\to\\video.MP4</pre>
</div>
"""


# Track the running job's output so the page can poll it.
_job_state = {"video": None, "state": None, "log": ""}
_job_lock = threading.Lock()


def _ffmpeg_available() -> bool:
    try:
        return subprocess.run(["ffmpeg", "-version"],
                              capture_output=True, timeout=5).returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _run_process_job(video_path: Path, interval: int):
    """Runs process.py in a subprocess and streams output into _job_state."""
    with _job_lock:
        _job_state["video"] = video_path.name
        _job_state["state"] = "running"
        _job_state["log"] = ""

    cmd = ["python", "process.py", "process", str(video_path), "--interval", str(interval)]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1)
        for line in proc.stdout:
            with _job_lock:
                _job_state["log"] += line
        proc.wait()
        with _job_lock:
            _job_state["state"] = "done" if proc.returncode == 0 else "failed"
    except Exception as e:
        with _job_lock:
            _job_state["state"] = "failed"
            _job_state["log"] += f"\nERROR: {e}\n"


@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        f = request.files.get("video")
        if not f or not f.filename:
            return redirect(url_for("upload"))

        # Save the uploaded file
        safe_name = re.sub(r'[^\w.\-]', '_', f.filename)
        dest = UPLOAD_DIR / safe_name
        f.save(dest)

        interval = int(request.form.get("interval") or 30)
        threading.Thread(target=_run_process_job, args=(dest, interval), daemon=True).start()
        return redirect(url_for("upload"))

    with _job_lock:
        job = dict(_job_state) if _job_state["video"] else None

    return render(_UPLOAD_BODY, page="upload", title="Process Video",
                  api_key_set=bool(os.environ.get("OPENAI_API_KEY")),
                  ffmpeg_ok=_ffmpeg_available(),
                  job_status=job)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  PackTrack  →  http://localhost:5001")
    print("=" * 60)
    print("  Search:  http://localhost:5001/")
    print("  Labels:  http://localhost:5001/labels")
    print("  Upload:  http://localhost:5001/upload")
    print("=" * 60 + "\n")
    app.run(host="0.0.0.0", port=5001, debug=False)
