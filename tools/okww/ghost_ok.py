"""Confirm the Windows ghost dialog (app not responding) with a native click.

The dialog is an OS window above the game surface, so PostMessage input cannot
reach it. Use the documented in-session PynputInteraction path, clicking the
OCR-located confirm button. The app then closes itself and the framework can
relaunch it cleanly on the next task.
"""
import ctypes
import os
import re

from ok import BaseTask
from ok.device.interaction_methods.pynput import PynputInteraction
from src.task.MouseResetTask import MouseResetTask


class Task(BaseTask):
    def reset_to_start(self):
        self.next_frame()

    def verify_start_state(self):
        # The game dropped out of fullscreen to a windowed 1600x900 during the hang.
        assert (self.width, self.height) in [(1920, 1080), (1600, 900)]
        frame = self.next_frame()
        texts = self.ocr(frame=frame)
        assert any(re.search("失去响应", b.name) for b in texts), "Ghost dialog not visible"

    def run(self):
        session = ctypes.c_ulong()
        expected = int(os.environ.get("PLAYSAGE_CHILD_SESSION_ID",
                                      os.environ.get("QUESTWEAVER_CHILD_SESSION_ID", "0")))
        assert expected > 1
        assert ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(session))
        assert session.value == expected
        frame = self.next_frame()
        self.screenshot("ghost_dialog")
        texts = self.ocr(frame=frame)
        self.log_info(str([(b.name, b.x, b.y) for b in texts]))
        ok_box = next(
            (b for b in texts if re.fullmatch("确定|確定", b.name.strip())), None
        )
        assert ok_box is not None, "Confirm button not found on ghost dialog"
        x = ok_box.x + ok_box.width // 2
        y = ok_box.y + ok_box.height // 2
        interaction = self.executor.interaction
        try:
            interaction.hwnd_window.bring_to_front()
        except Exception as e:
            self.log_info(f"bring_to_front ignored: {e}")
        native = PynputInteraction(interaction.capture, interaction.hwnd_window)
        mouse = self.get_task_by_class(MouseResetTask)
        enabled = mouse._enabled
        mouse._enabled = False
        native.check_clickable = False
        try:
            native.move(x, y)
            self.sleep(0.5)
            native.click(x, y, down_time=0.15)
        finally:
            native.check_clickable = True
            mouse._enabled = enabled
        self.sleep(25)
