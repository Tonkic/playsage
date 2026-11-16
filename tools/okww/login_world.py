"""Drive the native login flow until the game reaches the team world.

The executor runs one job at a time, so trigger tasks (Auto Login) stay
paused while this task owns the slot; wait_login() performs the same steps.
"""
import time

from ok import BaseTask
from src.task.DailyTask import DailyTask


class Task(BaseTask):
    def reset_to_start(self):
        self.daily = self.get_task_by_class(DailyTask)
        self.next_frame()

    def verify_start_state(self):
        assert not self.daily.in_team_and_world(), "Already in the world; nothing to log in"

    def run(self):
        # A previous run on this instance may have left the flag set, which
        # makes wait_login return without doing anything.
        self.daily.logged_in = False
        deadline = time.time() + 600
        logged = False
        while time.time() < deadline:
            if self.daily.wait_login():
                logged = True
                break
            self.sleep(3)
        assert logged, "Login did not reach the game world in time"
        self.sleep(5)
        self.next_frame()
        assert self.daily.in_team_and_world(), "World reached but team check failed"
        self.screenshot("logged_in_world")
