"""pydirectinput-based drag test in session 2: real SendInput input events."""
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
import pydirectinput

pydirectinput.FAILSAFE = False
pydirectinput.PAUSE = 0.02

# the puzzle is open. slot1 (毁灭者) at client (1432,345); screen = client + (8,31)?? 
# pydirectinput works in SCREEN pixels: the game window at (0,0) 1920x1080 → client == screen
sx, sy = 1432, 345
tx, ty = 1204, 486

print("moveTo slot", flush=True)
pydirectinput.moveTo(sx, sy)
time.sleep(0.5)
print("mouseDown", flush=True)
pydirectinput.mouseDown()
time.sleep(0.4)
# smooth interpolated drag with SendInput moves
cx, cy = pydirectinput.position()
print("pos after down:", cx, cy, flush=True)
for i in range(1, 31):
    nx = cx + (tx - cx) * i / 30
    ny = cy + (ty - cy) * i / 30
    pydirectinput.moveTo(int(nx), int(ny))
    time.sleep(0.04)
time.sleep(0.5)
print("pos at target:", pydirectinput.position(), flush=True)
print("mouseUp", flush=True)
pydirectinput.mouseUp()
time.sleep(1.2)
print("DONE", flush=True)
