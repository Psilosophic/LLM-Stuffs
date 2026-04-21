#!/usr/bin/env python3
"""PackTrack - web search UI. Run this then open http://localhost:5001"""

import re
import sqlite3
from pathlib import Path
from flask import Flask, request, render_template_string, send_file, abort

DB_PATH = "packtrack.db"

app = Flask(__name__)

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PackTrack</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body   { font-family: system-ui, sans-serif; background: #111; color: #ddd;
           max-width: 960px; margin: 0 auto; padding: 24px 16px; }
  h1     { font-size: 1.8rem; color: #4af; margin-bottom: 24px; }
  h1 span { font-size: 1rem; color: #666; font-weight: normal; margin-left: 8px; }
  form   { display: flex; gap: 8px; margin-bottom: 24px; }
  input  { flex: 1; padding: 12px 16px; font-size: 1rem;
           background: #222; border: 1px solid #444; color: #eee;
           border-radius: 8px; outline: none; }
  input:focus { border-color: #4af; }
  button { padding: 12px 24px; background: #4af; color: #000;
           font-weight: 700; font-size: 1rem; border: none;
           border-radius: 8px; cursor: pointer; white-space: nowrap; }
  button:hover { background: #6cf; }
  .meta  { color: #666; font-size: 0.85rem; margin-bottom: 16px; }
  .card  { background: #1c1c1c; border: 1px solid #333; border-radius: 10px;
           padding: 18px; margin-bottom: 16px; }
  .box   { font-size: 1.3rem; font-weight: 700; color: #4af; margin-bottom: 6px; }
  .time  { font-size: 0.82rem; color: #666; margin-bottom: 10px; }
  .label { font-size: 0.75rem; text-transform: uppercase; letter-spacing: .05em;
           color: #888; margin-top: 10px; }
  .val   { margin: 2px 0 8px; color: #ccc; font-size: 0.92rem; }
  img    { max-width: 100%; max-height: 240px; border-radius: 6px;
           margin-top: 10px; object-fit: cover; }
  .empty { text-align: center; padding: 60px; color: #555; font-size: 1.1rem; }
  .tip   { background: #1a2030; border: 1px solid #2a3a55; border-radius: 8px;
           padding: 14px 18px; font-size: 0.88rem; color: #89a; margin-bottom: 24px; }
</style>
</head>
<body>

<h1>📦 PackTrack <span>moving inventory</span></h1>

<form method="get" action="/">
  <input type="text" name="q" value="{{ query|e }}"
         placeholder="Search for anything: cables, kitchen stuff, soldering iron…"
         autofocus>
  <button type="submit">Find It</button>
</form>

{% if not query %}
<div class="tip">
  💡 <strong>How to search:</strong> type any item name, material, color, or box label.
  Try: <em>HDMI</em> &nbsp;·&nbsp; <em>box 7</em> &nbsp;·&nbsp; <em>cables</em>
  &nbsp;·&nbsp; <em>kitchen</em>
</div>
{% endif %}

{% if query %}
  {% if results %}
    <div class="meta">{{ results|length }} result(s) for "<strong>{{ query|e }}</strong>"</div>
    {% for r in results %}
    <div class="card">
      <div class="box">📦 {{ r.box_label or "Unknown Box" }}</div>
      <div class="time">{{ r.video_name }} &nbsp;·&nbsp; {{ r.time_fmt }}</div>

      {% if r.narration %}
      <div class="label">You said</div>
      <div class="val">{{ r.narration }}</div>
      {% endif %}

      <div class="label">Camera saw</div>
      <div class="val">{{ r.visual_description }}</div>

      {% if r.frame_path %}
      <img src="/frame/{{ r.frame_path }}" alt="frame thumbnail">
      {% endif %}
    </div>
    {% endfor %}
  {% else %}
    <div class="empty">Nothing found for "<strong>{{ query|e }}</strong>"</div>
  {% endif %}
{% endif %}

</body>
</html>"""


def _safe_query(raw: str) -> str:
    """Strip FTS5 special chars so plain words always work."""
    return re.sub(r'[^\w\s]', ' ', raw).strip()


@app.route("/")
def index():
    query = request.args.get("q", "").strip()
    results = []

    if query:
        safe_q = _safe_query(query)
        if safe_q and Path(DB_PATH).exists():
            conn = sqlite3.connect(DB_PATH)
            try:
                rows = conn.execute(
                    """SELECT pe.box_label, pe.narration, pe.visual_description,
                              pe.frame_path, pe.timestamp, s.video_file
                       FROM search_fts sf
                       JOIN packing_events pe ON sf.event_id = pe.id
                       JOIN sessions s ON pe.session_id = s.id
                       WHERE search_fts MATCH ?
                       ORDER BY rank
                       LIMIT 30""",
                    (safe_q,),
                ).fetchall()
            except Exception:
                rows = []
            conn.close()

            for box, narration, visual, frame_path, ts, video_file in rows:
                mins, secs = divmod(int(ts or 0), 60)
                results.append({
                    "box_label":         box,
                    "narration":         (narration or "")[:200],
                    "visual_description": (visual or "")[:200],
                    "frame_path":        frame_path,
                    "time_fmt":          f"{mins}:{secs:02d}",
                    "video_name":        Path(video_file).name if video_file else "",
                })

    return render_template_string(_HTML, query=query, results=results)


@app.route("/frame/<path:frame_path>")
def serve_frame(frame_path):
    p = Path(frame_path)
    if not p.exists() or p.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        abort(404)
    return send_file(p)


if __name__ == "__main__":
    print("PackTrack search UI → http://localhost:5001")
    app.run(host="0.0.0.0", port=5001, debug=False)
