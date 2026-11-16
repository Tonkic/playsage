"""Confirm the visually reviewed challenge exit dialog once."""
from ok import BaseTask
from src.task.DailyTask import DailyTask


class Task(BaseTask):
    def reset_to_start(self):
        self.daily = self.get_task_by_class(DailyTask)
        self.next_frame()

    def verify_start_state(self):
        assert self.daily.find_one([
            "confirm_btn_hcenter_vcenter", "confirm_btn_highlight_hcenter_vcenter"
        ]), "Expected challenge exit confirmation"

    def run(self):
        self.daily.click_dialog_right_button()
        self.daily.wait_in_team_and_world(time_out=600)
        self.next_frame()
        assert not self.daily.in_realm(), "Still inside challenge"
        self.screenshot("nightmare_exit_world")
