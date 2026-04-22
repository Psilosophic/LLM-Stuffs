#!/usr/bin/env python3
"""
One-shot: generate a static printable HTML file with QR labels embedded.
No dependencies at runtime — the HTML is standalone.

Usage:  python build_static_labels.py 1 100
"""

import argparse
import base64
import io
import sys
from pathlib import Path

import qrcode

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>PackTrack Labels — {prefix}-{start} to {prefix}-{end}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: system-ui, -apple-system, sans-serif;
    background: #f5f5f5;
    color: #222;
    padding: 20px;
  }}
  .controls {{
    max-width: 900px;
    margin: 0 auto 20px;
    background: white;
    padding: 20px;
    border-radius: 10px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  }}
  .controls h1 {{ color: #2563eb; margin-bottom: 8px; }}
  .controls p {{ color: #555; margin-bottom: 14px; line-height: 1.5; }}
  .btn {{
    background: #2563eb; color: white; border: none;
    padding: 12px 24px; font-size: 16px; font-weight: 600;
    border-radius: 8px; cursor: pointer;
  }}
  .btn:hover {{ background: #1e50c7; }}
  .sheet {{
    max-width: 900px;
    margin: 0 auto;
    display: grid;
    grid-template-columns: repeat({cols}, 1fr);
    gap: 14px;
  }}
  .label {{
    background: white;
    border: 1px solid #ccc;
    border-radius: 6px;
    padding: 12px;
    text-align: center;
    page-break-inside: avoid;
    break-inside: avoid;
  }}
  .label img {{
    width: 100%;
    height: auto;
    display: block;
    margin: 0 auto;
  }}
  .label .id {{
    font-family: ui-monospace, monospace;
    font-weight: 700;
    font-size: 20px;
    margin-top: 6px;
    letter-spacing: 0.03em;
  }}

  @media print {{
    body {{ background: white; padding: 0; }}
    .controls {{ display: none !important; }}
    .sheet {{ gap: 6px; max-width: 100%; }}
    .label {{ border: 1px solid #999; padding: 6px; }}
    @page {{ margin: 0.4in; }}
  }}
</style>
</head>
<body>

<div class="controls">
  <h1>📦 PackTrack Labels</h1>
  <p>
    {count} QR labels ({prefix}-{start} through {prefix}-{end}).
    Click <strong>Print</strong>, set margins to <em>Minimum</em>, scale to 100%,
    then tape them to your boxes. Scan with the PackTrack app to auto-detect
    which box you're filling.
  </p>
  <button class="btn" onclick="window.print()">🖨️ Print Labels</button>
</div>

<div class="sheet">
{labels}
</div>

</body>
</html>
"""


def qr_png_b64(box_id: str) -> str:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10, border=2,
    )
    qr.add_data(f"PACKTRACK:{box_id}")
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("start", type=int)
    ap.add_argument("end", type=int)
    ap.add_argument("--prefix", default="BOX")
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.end < args.start:
        sys.exit("end must be >= start")

    label_html = []
    for n in range(args.start, args.end + 1):
        box_id = f"{args.prefix}-{n}"
        b64 = qr_png_b64(box_id)
        label_html.append(
            f'  <div class="label"><img src="data:image/png;base64,{b64}" alt="{box_id}">'
            f'<div class="id">{box_id}</div></div>'
        )

    html = HTML_TEMPLATE.format(
        prefix=args.prefix,
        start=args.start,
        end=args.end,
        cols=args.cols,
        count=args.end - args.start + 1,
        labels="\n".join(label_html),
    )

    out = Path(args.out or f"packtrack_labels_{args.prefix}-{args.start}_to_{args.prefix}-{args.end}.html")
    out.write_text(html, encoding="utf-8")
    size_kb = out.stat().st_size / 1024
    print(f"Wrote {out} ({size_kb:.1f} KB, {args.end - args.start + 1} labels)")


if __name__ == "__main__":
    main()
