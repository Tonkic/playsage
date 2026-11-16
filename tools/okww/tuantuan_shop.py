"""A bounded, visually reviewed shop action using the existing native drag."""
import ctypes
import json
import os
import re

from ok import BaseTask
from ok.device.interaction_methods.pynput import PynputInteraction
from src.task.MouseResetTask import MouseResetTask


class Task(BaseTask):
    def reset_to_start(self):
        self.next_frame()

    def verify_start_state(self):
        assert (self.width, self.height) == (1920, 1080)
        self.wait_ocr(.16, .87, .26, .98, match=re.compile("冒险目标"), time_out=5,
                      raise_if_not_found=True)

    def tap(self, native, x, y, key="left"):
        native.move(x, y)
        self.sleep(.3)
        native.click(x, y, key=key, down_time=.15)
        self.sleep(.5)

    def drag_item(self, native, window, start, end, rotate=False):
        native.move(*start)
        self.sleep(.3)
        native.mouse_down(*start)
        try:
            self.sleep(.4)
            for step in range(1, 31):
                assert window.is_foreground()
                native.move(*(round(a + (b-a)*step/30) for a, b in zip(start, end)))
                self.sleep(.03)
            if rotate:
                native.click(*end, key="right", down_time=.1)
            self.sleep(.3)
        finally:
            native.check_clickable = False
            native.mouse_up()
            native.check_clickable = True
        self.sleep(.7)
        native.move(1056, 864)
        self.sleep(.2)
        native.click(1056, 864, down_time=.1)
        self.sleep(.3)
        self.next_frame()
        self.screenshot("tuantuan_drag_result")

    def fight_round(self, native):
        self.next_frame()
        assert self.ocr(.85, .88, .94, .93, match="开始")
        native.move(1718, 920)
        self.sleep(.3)
        native.click(1718, 920, down_time=.15)
        self.wait_ocr(.45, 0, .57, .07, match=re.compile("回合"),
                      time_out=20, raise_if_not_found=True)
        if self.ocr(.9, .15, .97, .2, match=re.compile(r"1\.0")):
            native.move(1800, 192)
            self.sleep(.3)
            native.click(1800, 192, down_time=.15)
        self.wait_ocr(.3, .1, .7, .3, match=re.compile("本回合胜利|本回合失败"),
                      time_out=90, raise_if_not_found=True)
        self.next_frame()
        self.screenshot("tuantuan_round_result")
        self.wait_ocr(.3, .1, .7, .3, match="本回合胜利", time_out=3,
                      raise_if_not_found=True)

    def continue_round(self, native, expected):
        self.next_frame()
        self.wait_ocr(.3, .1, .7, .3, match=re.compile("本回合胜利|本回合失败"),
                      time_out=5, raise_if_not_found=True)
        native.move(960, 980)
        self.sleep(.3)
        native.click(960, 980, down_time=.15)
        self.sleep(.8)
        self.next_frame()
        if self.ocr(.8, .87, .96, .94, match="进入下一回合"):
            native.move(1680, 980)
            self.sleep(.3)
            native.click(1680, 980, down_time=.15)
        self.wait_ocr(.56, .1, .73, .18, match=re.compile(f"回合{expected}.*商店"),
                      time_out=30, raise_if_not_found=True)

    def run(self):
        session = ctypes.c_ulong()
        expected = int(os.environ.get("PLAYSAGE_CHILD_SESSION_ID",
                                      os.environ.get("QUESTWEAVER_CHILD_SESSION_ID", "0")))
        assert expected > 1
        assert ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(session))
        assert session.value == expected
        interaction = self.executor.interaction
        interaction.hwnd_window.bring_to_front()
        assert self.wait_until(interaction.hwnd_window.is_foreground, time_out=3)
        native = PynputInteraction(interaction.capture, interaction.hwnd_window)
        mouse = self.get_task_by_class(MouseResetTask)
        enabled = mouse._enabled
        mouse._enabled = False
        try:
            self.tap(native, 395, 995)
            self.sleep(3)
            self.sleep(4)
            self.sleep(2)
            frame = self.next_frame()
            self.screenshot("tuantuan_shop_action")
            (self.artifact_directory / "visible.json").write_text(json.dumps([
                {"text": b.name, "x": b.x, "y": b.y} for b in self.ocr(frame=frame)
            ], ensure_ascii=False, indent=2), encoding="utf-8")
        finally:
            mouse._enabled = enabled
