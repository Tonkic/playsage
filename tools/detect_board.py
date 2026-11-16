import json
import sys

sys.path.insert(0, "tools")
sys.stdout.reconfigure(encoding="utf-8")
import httpio
from PIL import Image

import asyncio
import base64
import io


def shot():
    from PIL import ImageGrab
    return ImageGrab.grab().convert("RGB")


# grid in 1280x720 capture, measured empirically
GX, GY, CW, CH = 455, 195, 53.57, 51.67


def analyze(img):
    """Classify each cell: broken(⊘), red-chip, purple, grey-domino, empty."""
    out = []
    for r in range(6):
        line = []
        for c in range(7):
            x, y = int(GX + CW * (c + 0.5)), int(GY + CH * (r + 0.5))
            # sample 5x5 grid of points inside the cell
            red = grey = purple = dark = 0
            total = 0
            for dx in (-14, -7, 0, 7, 14):
                for dy in (-11, -5, 0, 5, 11):
                    xx, yy = x + dx, y + dy
                    if xx >= img.width or yy >= img.height:
                        continue
                    rr, gg, bb = img.getpixel((xx, yy))
                    total += 1
                    # red overlap highlight: strong red, low green/blue
                    if rr > 170 and gg < 110 and bb < 110:
                        red += 1
                    # purple energy chip: high blue, mid red/green
                    elif 120 < rr < 210 and 90 < gg < 170 and bb > 185:
                        purple += 1
                    # grey broken-ring / grey domino: channels close together, mid-bright
                    elif 85 < rr < 175 and 85 < gg < 175 and 95 < bb < 185 and abs(rr - gg) < 30 and abs(gg - bb) < 35:
                        grey += 1
                    elif rr < 75 and gg < 80 and bb < 95:
                        dark += 1
            # classification by dominance
            if red >= 4: k = "R"  # red overlapping chip
            elif purple >= 12: k = "E"  # purple chip
            elif grey >= 12: k = "G"  # grey domino chip
            elif grey >= 4 and dark >= 8: k = "X"  # broken cell (ring on dark)
            elif dark >= 12: k = "."
            elif red >= 2: k = "r"  # partial red
            elif purple >= 6: k = "e"  # partial purple
            else: k = "?"
            line.append(k)
        out.append(line)
    return out


def main():
    img = shot()
    img.save(r"D:\PlaySage\runs\observations\sra\detect_input.png")
    m = analyze(img)
    print("BOARD (R=red-chip E=energy G=grey X=broken .=empty):")
    for r, line in enumerate(m):
        print(f"r{r} " + " ".join(line), flush=True)
    broken = [(c, r) for r in range(6) for c in range(7) if m[r][c] == "X"]
    reds = [(c, r) for r in range(6) for c in range(7) if m[r][c] in ("R", "r")]
    print("broken cells:", broken, flush=True)
    print("red chip cells:", reds, flush=True)

main()
