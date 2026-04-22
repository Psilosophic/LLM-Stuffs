# PackTrack

Record your packing with a GoPro / action cam + narration → end of day, drop the video in → searchable inventory of what's in every box.

## Fastest possible setup (Windows)

1. **Install Python** once: https://www.python.org/downloads/ — check *Add Python to PATH*.
2. **Install ffmpeg** once:
   ```powershell
   winget install ffmpeg
   ```
   (restart PowerShell after.)
3. **Download this folder**, then double-click **`start.bat`**.

That's it. Your browser opens to the QR labels page. Print them, tape them to boxes, start packing.

## Getting your OpenAI key (only needed for video processing)

1. Sign up at https://platform.openai.com
2. Create an API key: https://platform.openai.com/api-keys
3. Add $5 of credit (covers your entire move + plenty extra).
4. Set it permanently in PowerShell:
   ```powershell
   setx OPENAI_API_KEY "sk-..."
   ```
   Close and reopen PowerShell. Then run `start.bat` again.

## Workflow

### Before packing
1. Open http://localhost:5001/labels
2. Set the range (e.g. BOX-1 to BOX-50).
3. Click **Generate** → click **Print**.
4. Tape one QR label on each empty box.

### While packing
1. Wear the DJI Osmo with the lapel mic clipped on.
2. Start recording. As you pack: **point the camera at the box's QR code**, then toss items in while saying what they are.
3. Example: *"Putting the soldering iron and Pi spare parts in this one."* (camera already saw the QR, so the box ID is locked in.)
4. When you move to a new box, point the camera at its QR first — that's the handoff.

### End of day
1. Copy the video off the camera to your PC.
2. Open http://localhost:5001/upload
3. Pick the file → click **Start Processing**. Wait.

### Finding stuff later
1. Open http://localhost:5001/
2. Search: *"HDMI cables"*, *"soldering"*, *"box 7"*, whatever.
3. You get the box ID, a thumbnail from the video, your own narration, and the camera's description.

## Cost

Roughly **$0.70–$1.10 per hour of video** using GPT-4o Mini + Whisper. A full move is typically under $5.

## Files

| File | What it does |
|------|--------------|
| `app.py` | The web app — run this |
| `start.bat` | Windows one-click launcher |
| `process.py` | CLI processor (same as web "Upload", for power users) |
| `labels.py` | CLI label generator (alt to web `/labels` page) |
| `search_ui.py` | Older search-only web UI — superseded by `app.py` |

## Troubleshooting

**"ffmpeg not found on PATH"** — Install ffmpeg (see setup above), restart your terminal.

**"OPENAI_API_KEY not set"** — See "Getting your OpenAI key" above. The **Labels** page works without it; processing video does not.

**Labels print too big/small** — On the Generate form, change Size (small/medium/large). In the print dialog, set margins to *Minimum* and scale to 100%.

**QR codes not being detected** — On Windows, `pyzbar` needs the zbar DLL. If missing, the vision model still catches QR codes from the frame (slightly slower / costs a hair more). To speed it up, install [this zbar build](https://github.com/NaturalHistoryMuseum/pyzbar/#windows) or just accept the fallback.
