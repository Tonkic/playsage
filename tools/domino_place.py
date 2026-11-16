import asyncio
import base64
import io
import json
import sys
import time

sys.path.insert(0, "tools")
sys.stdout.reconfigure(encoding="utf-8")
import httpio
from PIL import Image

# empirical grid in 1280x720 captures
GX, GY, CW, CH = 455, 195, 53.57, 51.67
OFF = (-8, -31)


def cell_center_1080(c, r):
    return (670.5 + 79.3 * (c + 0.5), 273.0 + 84.5 * (r + 0.5))


def sra_xy(c, r):
    x, y = cell_center_1080(c, r)
    return (int(x - 8), int(y - 31))


def board_matrix(img):
    out = []
    for r in range(6):
        line = []
        for c in range(7):
            x, y = int(GX + CW * (c + 0.5)), int(GY + CH * (r + 0.5))
            votes = {}
            for dx, dy in ((0, 0), (-10, 0), (10, 0), (0, -8), (0, 8)):
                rr, gg, bb = img.getpixel((x + dx, y + dy))
                if rr > 130 and gg > 110 and bb > 130 and (rr + gg + bb) > 420: k = "F"
                elif rr < 75 and gg < 80 and bb < 95: k = "."
                else: k = "?"
                votes[k] = votes.get(k, 0) + 1
            if votes.get("F", 0) >= 3: k = "F"
            else: k = max(votes, key=votes.get)
            line.append(k)
        return_taker = None
        out.append(line)
    return out


def filled_anywhere(m):
    return [(c, r) for r in range(6) for c in range(7) if m[r][c] == "F"]


async def shot():
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    async with streamablehttp_client("http://127.0.0.1:5000/mcp") as (rd, wr, _):
        async with ClientSession(rd, wr) as s:
            await s.initialize()
            res = await s.call_tool("sra_screenshot", {})
            for b in res.content:
                if b.type == "image":
                    return Image.open(io.BytesIO(base64.b64decode(b.data))).convert("RGB")
    raise RuntimeError("no image")


async def main():
    # two dominos: 先锋 domino -> cells (0,2),(1,2); 毁灭者 domino -> (2,2),(2,3)
    JOBS = [
        ("s5_xf", 1424 - 8, 749 - 31, (0, 2), [(0, 2), (1, 2)]),
        ("s6_hmz", 1672 - 8, 749 - 31, (2, 2), [(2, 2), (2, 3)]),
    ]
    for chip, sx, sy, anchor, cells in JOBS:
        cx = sum(p[0] for p in cells) / 2
        cy = sum(p[1] for p in cells) / 2
        tx, ty = sra_xy(int(round(cx - 0.5)) if False else int(cx * 0) + int(cell_center_1080(0, 0)[0]) - 8, 0)
        # simpler: compute the drop = the centroid cell center
        drop_x, drop_y = sra_xy(int(cx), int(cy))
        print(f"[{chip}] drop target ({drop_x},{drop_y})", flush=True)
        r = httpio.op("drag_to", from_x=sx, from_y=sy, to_x=drop_x, to_y=drop_y, duration=1.2)
        print(f"[{chip}] drag {r}", flush=True)
        time.sleep(0.9)
        img = await shot()
        m = board_matrix(img)
        filled = filled_anywhere(m)
        print(f"[{chip}] board after: {filled}", flush=True)
        img.save(rf"D:\PlaySage\runs\observations\sra\dom_{chip}.png")

asyncio.run(main())
