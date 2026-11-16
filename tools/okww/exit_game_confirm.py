"""Confirm the game-exit dialog by clicking the OCR-located exit button.

This dialog's buttons are inverted relative to the kick dialog: the LEFT
button exits, the right one returns to login. Locate by text, not position.
"""
import re

from ok import BaseTask
from src.task.DailyTask import DailyTask


class Task(BaseTask):
    def reset_to_start(self):
        self.daily = self.get_task_by_class(DailyTask)
        self.next_frame()

    def verify_start_state(self):
        frame = self.next_frame()
        texts = self.ocr(frame=frame)
        assert any(re.search("是否确定退出游戏|退出游戏", b.name) for b in texts), (
            "Exit dialog not visible"
        )

    def run(self):
        frame = self.next_frame()
        texts = self.ocr(frame=frame)
        self.log_info(str([(b.name, b.x, b.y) for b in texts]))
        self.screenshot("exit_dialog located")
        exit_box = next(
            (b for b in texts if re.fullmatch("退出游戏", b.name.strip())), None
        )
        assert exit_box is not None, "Exit game button not found"
        self.click(exit_box, after_sleep=2)
        self.sleep(25)
