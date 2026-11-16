"""Invoke the installed, registered OK-WW daily task and verify visible points."""

import json

from ok import BaseTask
from src.task.DailyTask import ADDITIONAL_TASKS, AUTO_FARM_NIGHTMARE_NEST, DailyTask


class Task(BaseTask):
    skip_failed_nests = False

    def reset_to_start(self):
        self.daily = self.get_task_by_class(DailyTask)
        self.daily.ensure_main(time_out=180)

    def verify_start_state(self):
        self.next_frame()
        assert self.daily.in_team_and_world(), "Expected the game world with an active team"

    def run(self):
        self.screenshot("playsage_daily_before")
        # A recovery harness can exclude the failed optional pass for that run.
        # The normal entry preserves all user settings. Never save an override
        # to the user's Config object or copy the native task logic.
        original_config = self.daily.config
        if self.skip_failed_nests:
            self.daily.config = dict(original_config)
            self.daily.config[ADDITIONAL_TASKS] = [
                item for item in original_config.get(ADDITIONAL_TASKS, [])
                if item != AUTO_FARM_NIGHTMARE_NEST
            ]
        try:
            self.daily.run()
        finally:
            self.daily.config = original_config
        self.daily.ensure_main(time_out=30)
        used_stamina, ready = self.daily.open_daily()
        points = self.daily.get_total_daily_points()
        self.screenshot("playsage_daily_verification")
        result = {"daily_points": points, "reward_ready": ready,
                  "observed_used_stamina": used_stamina, "native_daily_returned": True,
                  "skipped_optional_after_failure": (
                      [AUTO_FARM_NIGHTMARE_NEST] if self.skip_failed_nests else []),
                  "rewards_require_visual_review": True}
        (self.artifact_directory / "daily-result.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        assert ready and points >= 100, "Native routine returned but daily points are below 100"
