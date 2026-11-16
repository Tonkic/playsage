"""Read five event tabs already observed on the Activities sidebar."""
import json

from ok import BaseTask


class Task(BaseTask):
    def reset_to_start(self):
        # Read-only navigation from an already reviewed Activities page.
        self.next_frame()

    def verify_start_state(self):
        assert self.ocr(0, 0, 0.25, 0.13, match="推荐活动")

    def run(self):
        for title in ["无音消除", "团团勇者大乱斗", "凝月辉途", "心影映花", "故梦寻契"]:
            entry = self.wait_ocr(0.085, 0.14, 0.21, 0.9, match=title,
                                  time_out=15, raise_if_not_found=True)
            assert len(entry) == 1, f"Ambiguous event entry: {title}"
            self.click(entry[0], after_sleep=2)
            self.wait_ocr(0.55, 0.09, 0.99, 0.27, match=title,
                          time_out=20, settle_time=1, raise_if_not_found=True)
            frame = self.next_frame()
            self.screenshot("event_" + title)
            boxes = self.ocr(frame=frame)
            (self.artifact_directory / (title + ".json")).write_text(
                json.dumps([{"text": b.name, "x": b.x, "y": b.y} for b in boxes],
                           ensure_ascii=False, indent=2), encoding="utf-8"
            )
            assert boxes
