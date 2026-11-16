"""Final verified placement: HTTP ops + MCP screenshots + per-chip R-fix."""
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

GX0, GY0, GW, GH = 670.5 - 8, 273.0 - 31, 79.3, 84.5
TAB_GRID = (1410 - 8, 180 - 31)
TAB_STAR = (1552 - 8, 180 - 31)


def cell_px(c, r):
    # empirical grid position in the 1280x720 MCP captures (includes title bar offset)
    return (455 + 53.57 * (c + 0.5), 195 + 51.67 * (r + 0.5))


def board_matrix(img):
    sx = img.width / 1280.0
    sy = img.height / 720.0
    out = []
    for r in range(6):
        line = []
        for c in range(7):
            wx, wy = cell_px(c, r)
            x, y = int(wx * sx), int(wy * sy)
            votes = {}
            for dx, dy in ((0, 0), (-12, 0), (12, 0), (0, -9), (0, 9)):
                xx, yy = int(x + dx * sx), int(y + dy * sy)
                rr, gg, bb = img.getpixel((xx, yy))
                if rr > 200 and 150 < gg < 220 and 150 < bb < 220: k = "P"
                elif bb > 200 and 150 < gg < 230 and 100 < rr < 180: k = "B"
                elif rr > 200 and 150 < gg < 230 and 60 < bb < 120: k = "Y"
                elif 60 < rr < 115 and 60 < gg < 120 and 80 < bb < 145: k = "F"
                elif rr < 75 and gg < 80 and bb < 95: k = "."
                else: k = "?"
                votes[k] = votes.get(k, 0) + 1
            if votes.get("F"): k = "F"
            elif votes.get("Y", 0) >= 2: k = "Y"
            else: k = max(votes, key=votes.get)
            line.append(k)
        out.append(line)
    return out


async def shot():
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    async with streamablehttp_client("http://127.0.0.1:5000/mcp") as (rd, wr, _):
        async with ClientSession(rd, wr) as s:
            await s.initialize()
            res = await s.call_tool("sra_screenshot", {})
            for b in res.content:
                if b.type == "image":
                    from PIL import Image
                    return Image.open(io.BytesIO(base64.b64decode(b.data))).convert("RGB")
    raise RuntimeError("no image")


def filled(m, cells):
    return all(m[r][c] in ("P", "B", "?", "Y") for c, r in cells)


async def main():
    LAYOUT = [
        ("P_z2",  "grid", (1672-8, 345-31), [(0,4),(0,5),(1,4),(1,5),(2,5)]),
        ("T_ld",  "star", (1432-8, 345-31), [(1,0),(2,0),(2,1),(3,0)]),
        ("L_zhg", "star", (1672-8, 345-31), [(0,3),(1,3),(2,2),(2,3)]),
        ("Z_xb1", "grid", (1432-8, 780-31), [(2,4),(3,4),(3,5),(4,5)]),
        ("Z_xb2", "star", (1672-8, 562-31), [(5,4),(5,5),(6,3),(6,4)]),
        ("S_xb",  "star", (1672-8, 780-31), [(3,1),(4,0),(4,1),(5,0)]),
        ("S_ld2", "grid", (1672-8, 562-31), [(3,2),(3,3),(4,3),(4,4)]),
    ]

    # NO reset: L_ld and P_z1 are already placed correctly

    current_tab = None
    for chip, tab, slot, cells in LAYOUT:
        if tab != current_tab:
            txy = TAB_GRID if tab == "grid" else TAB_STAR
            httpio.op("click_point", mode="abs", x=txy[0], y=txy[1], after_sleep=0.9)
            current_tab = tab
        tc = cells and (sum(p[0] for p in cells) / len(cells), sum(p[1] for p in cells) / len(cells))
        tpx = int(GX0 + GW * (tc[0] + 0.5))
        tpy = int(GY0 + GH * (tc[1] + 0.5))
        httpio.op("drag_to", from_x=slot[0], from_y=slot[1], to_x=tpx, to_y=tpy, duration=1.5)
        time.sleep(0.9)

        placed = False
        img = await shot()
        m = board_matrix(img)
        if filled(m, cells):
            placed = True
            print(f"[{chip}] OK direct", flush=True)
        for rot in range(4):
            httpio.op("press_key", key="r", wait=0.5)
            img = await shot()
            m = board_matrix(img)
            if filled(m, cells):
                placed = True
                print(f"[{chip}] OK after R{rot+1}", flush=True)
                break
        if not placed:
            print(f"[{chip}] FAILED - cells:", flush=True)
            for line in m:
                print("   ", " ".join(line), flush=True)
            img.save(rf"D:\PlaySage\runs\observations\sra\fail_{chip}.png")
            return
        # deselect via the free cell (4,0)
        httpio.op("click_point", mode="abs", x=1027-8, y=315-31, after_sleep=0.4)
    print("ALL PLACED", flush=True)
    img = await shot()
    m = board_matrix(img)
    for line in m:
        print("   ", " ".join(line), flush=True)
    img.save(r"D:\PlaySage\runs\observations\sra\final_board.png")


if __name__ == "__main__":
    asyncio.run(main())
