"""Puzzle placement driver: persistent MCP session, ghost-verified chip drops.

Grid model: 7 cols x 6 rows, forbidden (4,2) and (6,5).
Cell center in 1080p window px: x = 670.5 + 79.3*(c+0.5), y = 273 + 84.5*(r+0.5)
"""
import asyncio
import base64
import io
import json
import sys
import time

from PIL import Image
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = "http://127.0.0.1:5000/mcp"
GW, GH = 79.3, 84.5
GX0, GY0 = 670.5, 273.0

def cell_px(c, r):
    return (GX0 + GW * (c + 0.5), GY0 + GH * (r + 0.5))

def cells_centroid(cells):
    cs = [p[0] for p in cells]; rs = [p[1] for p in cells]
    return (sum(cs) / len(cs), sum(rs) / len(rs))


class SRA:
    def __init__(self):
        self._ctx = None

    async def __aenter__(self):
        self._ctx = streamablehttp_client(URL)
        read, write, _ = await self._ctx.__aenter__()
        self.sess = ClientSession(read, write)
        await self.sess.__aenter__()
        await self.sess.initialize()
        return self

    async def __aexit__(self, *a):
        await self.sess.__aexit__(*a)
        await self._ctx.__aexit__(*a)

    async def op(self, method, **params):
        args = {"method": method, "parameters": json.dumps(params) if params else None}
        res = await self.sess.call_tool("sra_operator_call", args)
        ok = True
        for b in res.content:
            if b.type == "text":
                try:
                    d = json.loads(b.text)
                    ok = bool(d.get("success", True))
                except Exception:
                    pass
        return ok

    async def shot(self):
        res = await self.sess.call_tool("sra_screenshot", {})
        for b in res.content:
            if b.type == "image":
                return Image.open(io.BytesIO(base64.b64decode(b.data))).convert("RGB")
        raise RuntimeError("no image in screenshot response")

    async def revive(self):
        await self.op("active_window")
        await self.op("move_to", x=0.5, y=0.5)
        await asyncio.sleep(0.35)

    async def press(self, key, wait=0.5):
        await self.op("press_key", key=key, wait=wait)
        await asyncio.sleep(0.35)

    async def click(self, x, y, after=1.0):
        await self.revive()
        await self.op("click_point", mode="abs", x=x, y=y, after_sleep=after)
        await asyncio.sleep(0.3)


def classify(img):
    """Return 6x7 matrix of cell classes (samples 720p shot via 2/3 scale)."""
    sx = img.width / 1920.0
    sy = img.height / 1080.0
    out = []
    for r in range(6):
        line = []
        for c in range(7):
            px, py = cell_px(c, r)
            px, py = px * sx, py * sy
            # sample center + 4 offsets, majority vote
            votes = {}
            for dx, dy in ((0, 0), (-9, 0), (9, 0), (0, -7), (0, 7)):
                x = int(min(max(px + dx, 0), img.width - 1))
                y = int(min(max(py + dy, 0), img.height - 1))
                rr, gg, bb = img.getpixel((x, y))
                if rr > 200 and 150 < gg < 230 and 60 < bb < 120: k = "Y"
                elif rr > 200 and 150 < gg < 220 and 150 < bb < 220: k = "Ps" if gg > 178 else "Pg"
                elif bb > 200 and 150 < gg < 230 and 100 < rr < 180: k = "Bs" if gg > 192 else "Bg"
                elif 60 < rr < 115 and 60 < gg < 120 and 80 < bb < 145: k = "F"
                elif rr < 75 and gg < 80 and bb < 95: k = "."
                else: k = "?"
                votes[k] = votes.get(k, 0) + 1
            # prefer special classes if any vote
            if votes.get("F"): k = "F"
            elif votes.get("Y", 0) >= 2: k = "Y"
            else: k = max(votes, key=votes.get)
            line.append(k)
        out.append(line)
    return out


def ghost_cells(img, color):
    """Find ghost-tinted cells (samples 720p shot via 2/3 scale)."""
    sx = img.width / 1920.0
    sy = img.height / 1080.0
    found = set()
    for r in range(6):
        for c in range(7):
            px, py = cell_px(c, r)
            rr, gg, bb = img.getpixel((int(px * sx), int(py * sy)))
            if color == "p" and rr > 195 and 125 < gg < 182 and 160 < bb < 215:
                found.add((c, r))
            if color == "b" and 80 < rr < 125 and 140 < gg < 185 and 195 < bb < 235:
                found.add((c, r))
    return found


def norm(cells):
    mx = min(c for c, r in cells); my = min(r for c, r in cells)
    return sorted((c - mx, r - my) for c, r in cells)


async def place(sra, chip, slot, target_cells, color, tab=None, grab_offset=(0, 0)):
    """Grab chip from slot, rotate until ghost shape matches, position, drop."""
    if tab:
        await sra.click(*tab, after=1.0)
    gx, gy = slot
    await sra.revive()
    await sra.op("move_to", x=gx, y=gy)
    await asyncio.sleep(0.2)
    ok = await sra.op("mouse_down", x=gx, y=gy)
    if not ok:
        print(f"[{chip}] GRAB FAILED"); return False
    await asyncio.sleep(0.4)
    await sra.op("move_rel", x_offset=14, y_offset=-6)
    await asyncio.sleep(0.4)

    tx, ty = cells_centroid(target_cells)
    tpx = GX0 + GW * (tx + 0.5)
    tpy = GY0 + GH * (ty + 0.5)
    await sra.op("move_to", x=int(tpx), y=int(tpy))
    await asyncio.sleep(0.6)

    # rotation loop
    target_norm = norm(target_cells)
    placed_ghost = None
    for attempt in range(5):
        img = await sra.shot()
        ghost = ghost_cells(img, color)
        if ghost and norm(ghost) == target_norm:
            placed_ghost = ghost
            break
        await sra.press("r", wait=0.4)
    if placed_ghost is None:
        print(f"[{chip}] rotation never matched; ghost last seen, aborting (leave held)")
        return False

    # position: shift cursor by centroid delta
    gcx, gcy = cells_centroid(placed_ghost)
    dc = (tx - gcx) * GW
    dr = (ty - gcy) * GH
    if abs(dc) > 3 or abs(dr) > 3:
        img = await sra.shot()
        # cursor position unknown after moves; recompute from stored last cursor
    # track cursor ourselves
    return await finalize(sra, chip, target_cells, color, tpx, tpy, dc, dr)


async def finalize(sra, chip, target_cells, color, tpx, tpy, dc, dr):
    global CURSOR
    nx, ny = int(CURSOR[0] + dc), int(CURSOR[1] + dr)
    await sra.op("move_to", x=nx, y=ny)
    await asyncio.sleep(0.6)
    CURSOR = (nx, ny)
    img = await sra.shot()
    ghost = ghost_cells(img, color)
    if not ghost or norm(ghost) != norm(target_cells):
        print(f"[{chip}] ghost mismatch after shift: {sorted(ghost)}")
        return False
    ok = await sra.op("mouse_up", x=nx, y=ny)
    await asyncio.sleep(1.0)
    img = await sra.shot()
    m = classify(img)
    filled = all(m[r][c] in ("Ps", "Pg", "Bs", "Bg", "?", "Y") for c, r in target_cells)
    print(f"[{chip}] dropped ok={ok} verify={'OK' if filled else 'FAIL'}")
    for line in m:
        print("   ", " ".join(line))
    return ok and filled


CURSOR = (0.5 * 1920, 0.5 * 1080)


async def main():
    steps = json.loads(sys.argv[1]) if len(sys.argv) > 1 else []
    async with SRA() as sra:
        for st in steps:
            global CURSOR
            print("== step:", st["chip"])
            if st.get("tab"):
                await sra.click(*st["tab"], after=1.0)
            await sra.revive()
            sx, sy = st["slot"]
            tc = [tuple(t) for t in st["cells"]]
            tx, ty = cells_centroid(tc)
            tpx, tpy = GX0 + GW * (tx + 0.5), GY0 + GH * (ty + 0.5)
            # engage drag with smooth interpolated drag_to (relative mickeys don't trigger the game's drag)
            if not await sra.op("drag_to", from_x=sx, from_y=sy, to_x=int(tpx), to_y=int(tpy), duration=2.0):
                print(f"[{st['chip']}] GRAB FAILED"); continue
            await asyncio.sleep(0.6)
            CURSOR = (int(tpx), int(tpy))
            target_norm = norm(tc)
            matched = None
            for attempt in range(5):
                img = await sra.shot()
                ghost = ghost_cells(img, st["color"])
                if ghost and norm(ghost) == target_norm:
                    matched = ghost
                    print(f"[{st['chip']}] ghost matched after {attempt} rotations")
                    break
                await sra.press("r", wait=0.4)
            if matched is None:
                img = await sra.shot()
                ghost = ghost_cells(img, st["color"])
                print(f"[{chip if False else st['chip']}] NO MATCH, ghost={sorted(ghost)} target={target_norm} -- leaving held")
                continue
            gcx, gcy = cells_centroid(matched)
            dc = (tx - gcx) * GW
            dr = (ty - gcy) * GH
            nx, ny = int(CURSOR[0] + dc), int(CURSOR[1] + dr)
            await sra.op("move_to", x=nx, y=ny)
            await asyncio.sleep(0.6)
            CURSOR = (nx, ny)
            img = await sra.shot()
            ghost = ghost_cells(img, st["color"])
            if not ghost or norm(ghost) != target_norm:
                print(f"[{st['chip']}] ghost mismatch after shift: {sorted(ghost)} -- leaving held")
                continue
            ok = await sra.op("mouse_up", x=nx, y=ny)
            await asyncio.sleep(1.0)
            img = await sra.shot()
            m = classify(img)
            bad = [(c, r) for c, r in tc if m[r][c] not in ("Ps", "Pg", "Bs", "Bg", "?", "Y", "t")]
            print(f"[{st['chip']}] dropped ok={ok} verify={'OK' if not bad else 'FAIL ' + str(bad)}")
            for line in m:
                print("   ", " ".join(line))

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
