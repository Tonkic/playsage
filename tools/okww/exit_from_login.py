"""Exit the game cleanly from the login screen power button.

Run only after the kick dialog is dismissed. The framework relaunches the
game on the next submitted task, releasing the paged-out process memory.
"""
import re

from ok import BaseTask
from src.task.DailyTask import DailyTask


class Task(BaseTask):
    def reset_to_start(self):
        self.daily = self.get_task_by_class(DailyTask)
        self.next_frame()

    def verify_start_state(self):
        assert not self.daily.in_team_and_world(), "Unexpectedly still in the game world"

    def run(self):
        frame = self.next_frame()
        texts = self.ocr(frame=frame)
        names = [b.name for b in texts]
        self.log_info(str(names)[:500])
        assert any(re.search("登录|开始游戏|进入游戏|扫码|签名", n) for n in names), (
            "Not on the login screen"
        )
        self.screenshot("login_before_exit")
        self.click_relative(0.034, 0.966, after_sleep=3)
        self.wait_feature(
            ["confirm_btn_hcenter_vcenter", "confirm_btn_highlight_hcenter_vcenter"],
            time_out=30, settle_time=1, raise_if_not_found=True,
        )
        dialog = self.next_frame()
        self.screenshot("login_exit_dialog")
        dialog_texts = self.ocr(0.2, 0.2, 0.8, 0.8, frame=dialog)
        self.log_info(str([(b.name, b.x, b.y) for b in dialog_texts]))
        assert any(re.search("退出|确认|确定", b.name) for b in dialog_texts), (
            "Exit confirmation dialog not recognized"
        )
        self.daily.click_dialog_right_button()
        self.sleep(20)
