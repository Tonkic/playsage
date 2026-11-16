import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
subprocess.Popen([r"D:\Star Rail\Game\StarRail.exe"], cwd=r"D:\Star Rail\Game",
                 creationflags=0x00000008)  # DETACHED_PROCESS
print("launched")
for i in range(30):
    time.sleep(4)
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq StarRail.exe", "/FO", "CSV"],
                         capture_output=True).stdout.decode("gbk", errors="replace")
    if "StarRail.exe" in out:
        print(f"game process up at ~{(i+1)*4}s")
        break
else:
    print("game did not appear in 120s")
