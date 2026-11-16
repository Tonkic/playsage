"""Claim daily rewards only, using the registered DailyTask native methods.

Run after the stamina farm has done its part. Skips farming entirely; claims
activity tiers, mail, battle pass and the configured weekly garden check,
then reports the observed points for independent review.
"""
import json

from ok import BaseTask
from src.task.DailyTask import DailyTask


class Task(BaseTask):
    def reset_to_start(self):
        self.daily = self.get_task_by_class(DailyTask)
        self.daily.ensure_main(time_out=300)

    def verify_start_state(self):
        self.next_frame()
        assert self.daily.in_team_and_world(), "Expected the game world with an active team"

    def run(self):
        used, ready = self.daily.open_daily()
        points = self.daily.get_total_daily_points()
        self.log_info(f"before claim: used={used} ready={ready} points={points}")
        self.screenshot("claim_before")

        self.daily.claim_daily()
        self.daily.ensure_main(time_out=180)
        used, ready = self.daily.open_daily()
        points = self.daily.get_total_daily_points()
        self.log_info(f"after claim_daily: used={used} ready={ready} points={points}")

        self.daily.claim_mail()
        self.daily.ensure_main(time_out=180)
        self.daily.claim_battle_pass()
        self.daily.ensure_main(time_out=180)
        self.daily.run_additional_tasks()
        self.daily.ensure_main(time_out=180)

        used, ready = self.daily.open_daily()
        points = self.daily.get_total_daily_points()
        self.screenshot("claim_final")
        result = {"daily_points": points, "reward_ready": ready,
                  "observed_used_stamina": used,
                  "rewards_require_visual_review": True}
        (self.artifact_directory / "claim-result.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        assert ready and points >= 100, f"Points {points} below 100 or rewards not ready"
