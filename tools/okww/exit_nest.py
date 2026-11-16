"""Bounded recovery from the observed nightmare challenge through native APIs."""
import re

from ok import BaseTask
from src.task.DailyTask import DailyTask


class Task(BaseTask):
    def reset_to_start(self):
        self.daily = self.get_task_by_class(DailyTask)
        self.next_frame()

    def verify_start_state(self):
        assert self.daily.in_team_and_world()
        assert self.daily.in_realm(), "Expected the observed challenge exit icon"

    def run(self):
        self.send_key("esc", after_sleep=3)
        self.wait_until(
            lambda: self.daily.find_one([
                "confirm_btn_hcenter_vcenter", "confirm_btn_highlight_hcenter_vcenter"
            ]), time_out=30, raise_if_not_found=True
        )
        frame = self.next_frame()
        self.screenshot("nightmare_exit_dialog")
        boxes = self.ocr(0.15, 0.2, 0.85, 0.85, frame=frame)
        self.log_info(str([(box.name, box.x, box.y) for box in boxes]))
        assert any(re.search("退出|确认|取消", box.name) for box in boxes), "Exit dialog not visible"
