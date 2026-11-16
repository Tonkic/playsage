"""Accept the game's own hang dialog ("program not responding, will close").

The renderer stalled under system memory pressure; the game offers a graceful
close. Confirm it via OCR-located button, then wait for the process to exit.
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
        assert any(re.search("失去响应", b.name) for b in texts), "Hang dialog not visible"

    def run(self):
        frame = self.next_frame()
        texts = self.ocr(frame=frame)
        self.log_info(str([(b.name, b.x, b.y) for b in texts]))
        self.screenshot("hang_dialog")
        ok_box = next(
            (b for b in texts if re.fullmatch("确定|確定", b.name.strip())), None
        )
        assert ok_box is not None, "Confirm button not found on hang dialog"
        self.click(ok_box, after_sleep=2)
        self.sleep(25)
