#!/usr/bin/env python3
"""PackTrack - process a packing video into a searchable inventory database."""

import os
import sys
import re
import json
import sqlite3
import subprocess
import base64
import argparse
from pathlib import Path
from datetime import datetime

try:
    from openai import OpenAI
except ImportError:
    sys.exit("Missing dependency: pip install openai")

# QR decoding: use pyzbar if available, otherwise fall back to vision model
_HAS_PYZBAR = False
try:
    from pyzbar.pyzbar import decode as qr_decode
    from PIL import Image as _PIL_Image
    _HAS_PYZBAR = True
except ImportError:
    pass

DB_PATH = Path("packtrack.db")
FRAMES_DIR = Path("frames")


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def init_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            video_file   TEXT    NOT NULL,
            processed_at TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS packing_events (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id         INTEGER NOT NULL,
            timestamp          REAL    NOT NULL,
            box_label          TEXT,
            narration          TEXT,
            visual_description TEXT,
            frame_path         TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );

        -- Full-text search index
        CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(
            box_label,
            narration,
            visual_description,
            event_id   UNINDEXED,
            frame_path UNINDEXED,
            tokenize = "unicode61"
        );
    """)
    conn.commit()
    return conn


def insert_event(conn: sqlite3.Connection, session_id: int, timestamp: float,
                 box_label: str | None, narration: str,
                 description: str, frame_path: str):
    cur = conn.execute(
        """INSERT INTO packing_events
           (session_id, timestamp, box_label, narration, visual_description, frame_path)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (session_id, timestamp, box_label, narration, description, frame_path),
    )
    event_id = cur.lastrowid
    conn.execute(
        """INSERT INTO search_fts
           (event_id, box_label, narration, visual_description, frame_path)
           VALUES (?, ?, ?, ?, ?)""",
        (event_id, box_label or "", narration, description, frame_path),
    )


# ---------------------------------------------------------------------------
# ffmpeg helpers
# ---------------------------------------------------------------------------

def check_ffmpeg():
    if subprocess.run(["ffmpeg", "-version"], capture_output=True).returncode != 0:
        sys.exit("ffmpeg not found. Install it: https://ffmpeg.org/download.html")


def extract_frames(video_path: Path, session_id: int, interval: int) -> list[dict]:
    """Pull one JPEG every `interval` seconds."""
    out_dir = FRAMES_DIR / str(session_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    pattern = str(out_dir / "frame_%06d.jpg")
    cmd = [
        "ffmpeg", "-i", str(video_path),
        "-vf", f"fps=1/{interval}",
        "-q:v", "3",
        pattern, "-y",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"ffmpeg frame extraction failed:\n{result.stderr}")

    frames = []
    for f in sorted(out_dir.glob("frame_*.jpg")):
        frame_num = int(f.stem.split("_")[1])
        frames.append({"path": f, "timestamp": float((frame_num - 1) * interval)})

    print(f"  Extracted {len(frames)} frames (1 per {interval}s)")
    return frames


def extract_audio(video_path: Path) -> Path:
    audio_path = video_path.with_suffix(".tmp.wav")
    cmd = ["ffmpeg", "-i", str(video_path), "-ar", "16000", "-ac", "1",
           str(audio_path), "-y"]
    subprocess.run(cmd, capture_output=True, check=True)
    return audio_path


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------

def transcribe(video_path: Path, client: OpenAI) -> list[dict]:
    print("  Transcribing audio (Whisper)...")
    audio_path = extract_audio(video_path)
    try:
        with open(audio_path, "rb") as f:
            resp = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )
        segments = [
            {"start": s.start, "end": s.end, "text": s.text.strip()}
            for s in resp.segments
        ]
    finally:
        audio_path.unlink(missing_ok=True)

    print(f"  Got {len(segments)} transcript segments")
    return segments


# ---------------------------------------------------------------------------
# Box-label tracking
# ---------------------------------------------------------------------------

# Patterns that signal a new container declaration
_BOX_PATTERNS = [
    r'\b(?:this is |going into |putting (?:this )?(?:in|into) )?box\s+(\w+)',
    r'\b(?:this is |going into |putting (?:this )?(?:in|into) )?bin\s+(\w+)',
    r'\b(?:this is |going into |putting (?:this )?(?:in|into) )?tote\s+(\w+)',
    r'\b(?:this is |going into |putting (?:this )?(?:in|into) )?crate\s+(\w+)',
    r'\b(?:this is |going into |putting (?:this )?(?:in|into) )?container\s+(\w+)',
    r'\b(kitchen|bathroom|bedroom|garage|office|living room|basement)\s+box',
]


def detect_box_label(text: str) -> str | None:
    low = text.lower()
    for pat in _BOX_PATTERNS:
        m = re.search(pat, low)
        if m:
            label = m.group(1) if m.lastindex else m.group(0)
            return label.strip().title()
    return None


def build_box_timeline(segments: list[dict]) -> list[tuple[float, str]]:
    """Return [(timestamp, label)] whenever a new box is declared."""
    timeline = []
    for seg in segments:
        label = detect_box_label(seg["text"])
        if label:
            timeline.append((seg["start"], label))
    return timeline


def current_box_at(timestamp: float, timeline: list[tuple[float, str]]) -> str | None:
    label = None
    for t, l in timeline:
        if t <= timestamp + 5:   # small look-ahead for label said just after placing
            label = l
        else:
            break
    return label


def narration_near(timestamp: float, segments: list[dict], window: float = 25.0) -> str:
    parts = []
    for seg in segments:
        mid = (seg["start"] + seg["end"]) / 2
        if abs(mid - timestamp) <= window:
            parts.append(seg["text"])
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Vision analysis
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# QR code detection
# ---------------------------------------------------------------------------

_PACKTRACK_PREFIX = "PACKTRACK:"


def decode_qr_from_frame(frame_path: Path) -> str | None:
    """
    Try to read a PackTrack QR code from the frame.
    Uses pyzbar (fast, local) when available; otherwise skips — the vision
    model will catch it in the prompt.
    """
    if not _HAS_PYZBAR:
        return None
    try:
        img = _PIL_Image.open(frame_path)
        for obj in qr_decode(img):
            data = obj.data.decode("utf-8", errors="ignore")
            if data.startswith(_PACKTRACK_PREFIX):
                return data[len(_PACKTRACK_PREFIX):]   # e.g. "BOX-7"
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Vision analysis
# ---------------------------------------------------------------------------

_VISION_PROMPT = """\
You are analyzing a frame from a first-person packing video.
The person narrated nearby: "{narration}"

Look for a QR code label on any box or bin. If you see one that starts with
"PACKTRACK:" report the full code value (e.g. "PACKTRACK:BOX-7").

Then in 2-3 short sentences describe:
- What specific items / objects are clearly visible
- Which box or container is in the frame (use the QR label if visible)
- What appears to be actively being placed or handled

Be specific about item names. Skip pleasantries."""


def analyze_frame(frame_path: Path, narration: str, client: OpenAI) -> tuple[str, str | None]:
    """Returns (description, qr_box_label_or_None)."""
    # Try fast local QR decode first
    qr_label = decode_qr_from_frame(frame_path)

    with open(frame_path, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode()

    prompt = _VISION_PROMPT.format(narration=narration[:300])
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "low"}},
            ],
        }],
        max_tokens=180,
    )
    description = resp.choices[0].message.content.strip()

    # If pyzbar missed it, try to parse from vision model response
    if not qr_label:
        m = re.search(r'PACKTRACK:(\S+)', description)
        if m:
            qr_label = m.group(1).rstrip('.,)"\'')

    return description, qr_label


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def process_video(video_path: Path, client: OpenAI, interval: int):
    if not video_path.exists():
        sys.exit(f"File not found: {video_path}")

    conn = init_db()

    print(f"\nProcessing: {video_path.name}")
    cur = conn.execute(
        "INSERT INTO sessions (video_file, processed_at) VALUES (?, ?)",
        (str(video_path), datetime.now().isoformat()),
    )
    session_id = cur.lastrowid
    conn.commit()

    segments = transcribe(video_path, client)
    box_timeline = build_box_timeline(segments)
    print(f"  Detected {len(box_timeline)} box declarations in narration")

    frames = extract_frames(video_path, session_id, interval)

    print(f"  Analyzing {len(frames)} frames with GPT-4o Mini vision...")
    if _HAS_PYZBAR:
        print("  (pyzbar available — QR codes will be decoded locally before vision call)")
    else:
        print("  (pyzbar not installed — QR codes detected via vision model; install pyzbar for speed)")

    qr_carry: str | None = None   # last seen QR label; persist across frames

    for i, frame in enumerate(frames, 1):
        ts = frame["timestamp"]
        narration = narration_near(ts, segments)
        description, qr_label = analyze_frame(frame["path"], narration, client)

        # QR label wins; narration-parsed label is the fallback
        if qr_label:
            qr_carry = qr_label
        box_label = qr_carry or current_box_at(ts, box_timeline)

        insert_event(conn, session_id, ts, box_label, narration,
                     description, str(frame["path"]))

        mins, secs = divmod(int(ts), 60)
        src = "QR" if qr_carry else ("narr" if box_label else "none")
        box_str = f"[{box_label} ({src})]" if box_label else "[no box]"
        print(f"    {i}/{len(frames)} | {mins}:{secs:02d} | {box_str:20s} | {description[:60]}...")

    conn.commit()
    conn.close()
    print(f"\nDone. Database: {DB_PATH.resolve()}")
    print("Search with:  python process.py search \"HDMI cables\"")
    print("Web UI:       python search_ui.py")


# ---------------------------------------------------------------------------
# CLI search (quick, no browser needed)
# ---------------------------------------------------------------------------

def search_cli(query: str):
    if not DB_PATH.exists():
        sys.exit(f"No database found at {DB_PATH}. Process a video first.")

    # Escape FTS special chars
    safe_q = re.sub(r'[^\w\s]', ' ', query).strip()
    if not safe_q:
        sys.exit("Empty query")

    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        """SELECT pe.box_label, pe.narration, pe.visual_description,
                  pe.frame_path, pe.timestamp, s.video_file
           FROM search_fts sf
           JOIN packing_events pe ON sf.event_id = pe.id
           JOIN sessions s ON pe.session_id = s.id
           WHERE search_fts MATCH ?
           ORDER BY rank
           LIMIT 20""",
        (safe_q,),
    ).fetchall()
    conn.close()

    if not rows:
        print(f"Nothing found for: {query}")
        return

    print(f"\n{len(rows)} result(s) for \"{query}\":\n")
    for box, narration, visual, frame_path, ts, video_file in rows:
        mins, secs = divmod(int(ts or 0), 60)
        print(f"  BOX:      {box or 'unknown'}")
        print(f"  Video:    {Path(video_file).name}  @  {mins}:{secs:02d}")
        print(f"  You said: {(narration or '')[:120]}")
        print(f"  Camera:   {(visual or '')[:120]}")
        print(f"  Frame:    {frame_path}")
        print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="PackTrack — video packing inventory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python process.py process GoPro_0042.MP4
  python process.py process GoPro_0042.MP4 --interval 20
  python process.py search "soldering iron"
  python process.py search "HDMI"
""",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("process", help="Process a video file")
    p.add_argument("video", help="Path to video file (MP4, MOV, etc.)")
    p.add_argument("--interval", type=int, default=30,
                   help="Seconds between frame grabs (default: 30)")

    s = sub.add_parser("search", help="Search the database (CLI)")
    s.add_argument("query", help="What to search for")

    args = parser.parse_args()

    if args.cmd == "process":
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            sys.exit("Set the OPENAI_API_KEY environment variable first.")
        check_ffmpeg()
        client = OpenAI(api_key=key)
        process_video(Path(args.video), client, args.interval)

    elif args.cmd == "search":
        search_cli(args.query)


if __name__ == "__main__":
    main()
