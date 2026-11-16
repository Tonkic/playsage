"""Restore a logged-in world through native recovery without running dailies."""
from ok import BaseTask
from src.task.DailyTask import DailyTask


class Task(BaseTask):
    def reset_to_start(self):
        self.daily = self.get_task_by_class(DailyTask)
        self.daily.ensure_main(time_out=600)

    def verify_start_state(self):
        self.next_frame()
        assert self.daily.in_team_and_world()

    def run(self):
        self.screenshot("recovered_world")
