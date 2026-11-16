"""Open the observed terminal Activities entry and record the visible page."""
import json
import re

from ok import BaseTask
from src.task.DailyTask import DailyTask


class Task(BaseTask):
    def reset_to_start(self):
        self.daily = self.get_task_by_class(DailyTask)
        self.daily.ensure_main(time_out=60)

    def verify_start_state(self):
        self.next_frame()
        assert self.daily.in_team_and_world() and not self.daily.in_realm()

    def run(self):
        self.daily.open_esc_menu()
        entry = self.wait_ocr(0.42, 0.22, 0.57, 0.34, match="活动",
                              time_out=30, settle_time=1, raise_if_not_found=True)
        assert len(entry) == 1, "Activities entry is ambiguous"
        self.click(entry[0], after_sleep=3)
        self.wait_ocr(0, 0, 0.25, 0.13, match=re.compile("活动"), time_out=30,
                      settle_time=1, raise_if_not_found=True)
        frame = self.next_frame()
        height, width = frame.shape[:2]
        assert (width, height) == (1920, 1080)
        self.screenshot("playsage_activities")
        boxes = self.ocr(frame=frame)
        (self.artifact_directory / "activities-visible.json").write_text(
            json.dumps([{"text": b.name, "x": b.x, "y": b.y,
                         "width": b.width, "height": b.height} for b in boxes],
                       ensure_ascii=False, indent=2), encoding="utf-8"
        )
        assert boxes, "Activity page OCR unavailable; visually inspect screenshot"
