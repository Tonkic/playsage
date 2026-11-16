"""Capture a disconnect dialog for manual review; never dismiss or reconnect."""

from ok import BaseTask
from src.task.DailyTask import DailyTask


class Task(BaseTask):
    def reset_to_start(self):
        self.daily = self.get_task_by_class(DailyTask)
        self.next_frame()

    def verify_start_state(self):
        assert self.daily.find_one(
            ["confirm_btn_hcenter_vcenter", "confirm_btn_highlight_hcenter_vcenter"]
        ), "Expected the disconnect confirmation dialog"

    def run(self):
        frame = self.next_frame()
        self.screenshot("disconnect_requires_manual_review")
        texts = self.ocr(0.15, 0.2, 0.9, 0.8, frame=frame)
        self.log_info(str([(b.name, b.x, b.y) for b in texts]))
        # Generic login text cannot distinguish a network failure from a warning.
        raise RuntimeError(
            "Disconnect requires manual review; automatic dismissal and relogin are disabled"
        )
