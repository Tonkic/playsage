import json
import sys
import time
from urllib.request import Request, urlopen

sys.path.insert(0, "tools")
sys.stdout.reconfigure(encoding="utf-8")
from PIL import ImageGrab

# grid in 1280x720 screen grabs (fullscreen)
GX, GY, CW, CH = 455, 195, 53.57, 51.67
OFF = (-8, -31)  # SRA coords = client - (8,31); client == screen here


def api(method, **params):
    req = Request("http://127.0.0.1:5000/api/operator/call",
                  data=json.dumps({"method": method, "params": params}).encode(),
                  method="POST", headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode()).get("success", False)
    except Exception as e:
        print("err:", e, flush=True)
        return False


def grab():
    return ImageGrab.grab().convert("RGB")


def classify(img):
    out = []
    for r in range(6):
        line = []
        for c in range(7):
            x, y = int(GX + CW * (c + 0.5)), int(GY + CH * (r + 0.5))
            votes = {}
            for dx, dy in ((0, 0), (-12, 0), (12, 0), (0, -9), (0, 9)):
                rr, gg, bb = img.getpixel((x + dx, y + dy))
                # purple energy chip
                if 120 < rr < 210 and 90 < gg < 170 and bb > 185: k = "E"
                # red overlap highlight
                elif rr > 170 and gg < 110 and bb < 110: k = "R"
                # grey domino / broken ring
                elif 85 < rr < 175 and 85 < gg < 175 and 95 < bb < 185 and abs(rr - gg) < 30: k = "G"
                elif rr < 75 and gg < 80 and bb < 95: k = "."
                else: k = "?"
                votes[k] = votes.get(k, 0) + 1
            line.append(max(votes, key=votes.get))
        out.append(line)
    return out


def cells_filled(m, cells):
    return all(m[r][c] in ("E", "G", "?", "R") for c, r in cells)


def sra_xy(c, r):
    x = GX - 0 + CW * (c + 0.5) - 0
    y = GY - 0 + CH * (r + 0.5)
    return (int(x - 8), int(y - 31))


def main():
    # chips: slot SRA coords, target cells, expected color
    CHIPS = [
        ("hmz1", 1424, 314, [(0,0),(1,0),(1,1),(2,1)], "E"),
        ("xf1",  1672, 314, [(3,0),(4,0),(3,1),(4,1)], "E"),
        ("ds1",  1424, 531, [(5,0),(5,1),(5,2),(6,2)], "E"),
        ("hmz2", 1672, 749, [(0,3),(0,4)], "G"),
        ("xf2",  1424, 749, [(3,3),(4,3)], "G"),
    ]
    t0 = time.time()
    def log(msg):
        print(f"[{time.time()-t0:5.1f}s] {msg}", flush=True)

    for chip, sx, sy, cells, col in CHIPS:
        tcx = sum(p[0] for p in cells) / len(cells)
        tcy = sum(p[1] for p in cells) / len(cells)
        tpx, tpy = sra_xy(tcx, tcy)
        placed = False
        for attempt in range(2):
            ok = api("drag_to", from_x=sx, from_y=sy, to_x=tpx, to_y=tpy, duration=1.5)
            time.sleep(0.9)
            m = classify(grab())
            if cells_filled(m, cells):
                placed = True
                log(f"[{chip}] OK direct")
                break
            # rotate: the placed chip is auto-selected
            for rot in range(4):
                api("press_key", key="r", wait=0.5)
                m = classify(grab())
                if cells_filled(m, cells):
                    placed = True
                    log(f"[{chip}] OK after R{rot+1}")
                    break
            if placed:
                break
            # move-fix: drag the placed chip by the measured delta
            act = [(c, r) for r in range(6) for c in range(7) if m[r][c] in ("E", "G", "?")]
            if act:
                acx = sum(p[0] for p in act) / len(act)
                acy = sum(p[1] for p in act) / len(act)
                dc = tcx - acx
                dr = tcy - acy
                fx = GX + CW * (acx + 0.5) - 8
                fy = GY + CH * (acy + 0.5) - 31
                t2x = int(fx + dc * CW)
                t2y = int(fy + dr * CH)
                api("drag_to", from_x=int(fx), from_y=int(fy), to_x=t2x, to_y=t2y, duration=1.2)
                time.sleep(0.9)
                m = classify(grab())
                if cells_filled(m, cells):
                    placed = True
                    log(f"[{chip}] OK after move-fix")
                    break
            log(f"[{chip}] attempt {attempt} failed")
        if not placed:
            log(f"[{chip}] GIVING UP")
            grab().save(rf"D:\PlaySage\runs\observations\sra\fail3_{chip}.png")
            return
        # deselect at a safe empty cell
        api("click_point", mode="abs", x=1142, y=580, after_sleep=0.5)
    log("ALL 5 PLACED - clicking finish")
    api("click_point", mode="abs", x=948, y=942, after_sleep=2.5)
    api("click_point", mode="abs", x=1166, y=683, after_sleep=2)
    log("SUBMITTED")


if __name__ == "__main__":
    main()
