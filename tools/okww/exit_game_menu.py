"""Exit the game through its own menu after a visually reviewed performance stall.

Bounded recovery: open the Esc menu, locate the exit entry by OCR, verify the
confirmation dialog contents, then confirm. Never kills the protected process.
"""
import re

from ok import BaseTask
from src.task.DailyTask import DailyTask


class Task(BaseTask):
    def reset_to_start(self):
        self.daily = self.get_task_by_class(DailyTask)
        self.next_frame()

    def verify_start_state(self):
        assert self.daily.in_team_and_world(), "Expected the game world before opening the menu"

    def run(self):
        self.screenshot("before_exit_menu")
        self.send_key("esc", after_sleep=3)
        self.wait_feature("esc_setting", time_out=60, settle_time=1, raise_if_not_found=True)
        self.screenshot("esc_menu_open")
        frame = self.next_frame()
        boxes = self.ocr(0.6, 0.88, 1.0, 1.0, frame=frame)
        self.log_info(str([(b.name, b.x, b.y, b.width, b.height) for b in boxes]))
        exit_box = next((b for b in boxes if re.search("退出", b.name)), None)
        assert exit_box is not None, "Exit entry not visible in the menu bottom strip"
        self.click(exit_box, after_sleep=3)
        self.wait_feature(
            ["confirm_btn_hcenter_vcenter", "confirm_btn_highlight_hcenter_vcenter"],
            time_out=30, settle_time=1, raise_if_not_found=True,
        )
        dialog = self.next_frame()
        self.screenshot("game_exit_dialog")
        texts = self.ocr(0.2, 0.2, 0.8, 0.8, frame=dialog)
        self.log_info(str([(b.name, b.x, b.y) for b in texts]))
        assert any(re.search("退出|确认|确定", b.name) for b in texts), (
            "Exit confirmation dialog not recognized"
        )
        self.daily.click_dialog_right_button()
        self.sleep(15)
        self.screenshot("after_exit_click")
