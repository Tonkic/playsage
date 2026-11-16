import ctypes
import sys

sys.stdout.reconfigure(encoding="utf-8")
SPI_GETMOUSE = 0x0003
SPI_SETMOUSE = 0x0004
SPI_SETMOUSESPEED = 0x0071
ui = ctypes.windll.user32
old = (ctypes.c_int * 3)()
ui.SystemParametersInfoW(SPI_GETMOUSE, 0, old, 0)
print("old mouse params:", list(old), flush=True)
new = (ctypes.c_int * 3)(0, 0, 0)
ok1 = ui.SystemParametersInfoW(SPI_SETMOUSE, 0, new, 0)
ok2 = ui.SystemParametersInfoW(SPI_SETMOUSESPEED, 0, ctypes.c_int(10), 0)
print("set:", ok1, ok2, flush=True)
