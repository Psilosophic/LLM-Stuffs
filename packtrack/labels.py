#!/usr/bin/env python3
"""
PackTrack Label Generator
Generates printable QR-code box labels as a PDF or PNG sheet.

Usage:
  python labels.py 1 20          # labels for Box 1 through Box 20
  python labels.py 1 20 --pdf    # output as PDF instead of PNG sheet
  python labels.py 1 20 --prefix "TOTE"   # TOTE-1 through TOTE-20
"""

import argparse
import math
import sys
from pathlib import Path

try:
    import qrcode
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit("Run: pip install qrcode[pil] Pillow")


# ---------------------------------------------------------------------------
# Single label
# ---------------------------------------------------------------------------

def make_label(box_id: str, size_px: int = 400) -> Image.Image:
    """Return a square PIL image with the QR code and human-readable label."""
    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # high redundancy
        box_size=10,
        border=2,
    )
    # Encode as "PACKTRACK:BOX-7" so the vision prompt knows the format
    qr.add_data(f"PACKTRACK:{box_id}")
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_img = qr_img.resize((size_px, size_px), Image.NEAREST)

    # Add label text below the QR code
    label_height = max(60, size_px // 5)
    canvas = Image.new("RGB", (size_px, size_px + label_height), "white")
    canvas.paste(qr_img, (0, 0))

    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                                  label_height - 10)
    except OSError:
        font = ImageFont.load_default()

    text = box_id
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    x = (size_px - text_w) // 2
    draw.text((x, size_px + 5), text, fill="black", font=font)

    return canvas


# ---------------------------------------------------------------------------
# Sheet layout
# ---------------------------------------------------------------------------

def make_sheet(labels: list[Image.Image], cols: int = 3) -> Image.Image:
    """Tile labels in a grid, A4-ish proportions."""
    if not labels:
        return Image.new("RGB", (100, 100), "white")

    lw, lh = labels[0].size
    pad = 20
    rows = math.ceil(len(labels) / cols)

    sheet_w = cols * lw + (cols + 1) * pad
    sheet_h = rows * lh + (rows + 1) * pad
    sheet = Image.new("RGB", (sheet_w, sheet_h), "#f0f0f0")

    for i, lbl in enumerate(labels):
        row, col = divmod(i, cols)
        x = pad + col * (lw + pad)
        y = pad + row * (lh + pad)
        sheet.paste(lbl, (x, y))

    return sheet


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate PackTrack box labels")
    parser.add_argument("start", type=int, help="First box number")
    parser.add_argument("end",   type=int, help="Last box number (inclusive)")
    parser.add_argument("--prefix", default="BOX", help="Label prefix (default: BOX)")
    parser.add_argument("--pdf",    action="store_true", help="Save as PDF instead of PNG")
    parser.add_argument("--cols",   type=int, default=3, help="Columns per row (default: 3)")
    parser.add_argument("--size",   type=int, default=380, help="Label size in px (default: 380)")
    args = parser.parse_args()

    if args.end < args.start:
        sys.exit("end must be >= start")

    ids = [f"{args.prefix}-{n}" for n in range(args.start, args.end + 1)]
    print(f"Generating {len(ids)} labels: {ids[0]} → {ids[-1]}")

    labels = [make_label(box_id, args.size) for box_id in ids]
    sheet = make_sheet(labels, cols=args.cols)

    if args.pdf:
        out = Path(f"packtrack_labels_{ids[0]}_{ids[-1]}.pdf")
        # PDF needs RGB images
        pages = [make_sheet(labels[i:i + args.cols * 4], cols=args.cols)
                 for i in range(0, len(labels), args.cols * 4)]
        pages[0].save(out, save_all=True, append_images=pages[1:])
    else:
        out = Path(f"packtrack_labels_{ids[0]}_{ids[-1]}.png")
        sheet.save(out)

    print(f"Saved: {out.resolve()}")
    print(f"\nTip: print at 100% scale, laminate, tape to boxes before you start packing.")
    print(f"The QR codes encode PACKTRACK:BOX-N — the vision model reads these automatically.")


if __name__ == "__main__":
    main()
