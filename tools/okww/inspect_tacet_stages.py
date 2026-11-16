"""Inspect Tacet Elimination stage availability without starting a stage."""
import json
import re

from ok import BaseTask


class Task(BaseTask):
    def reset_to_start(self):
        self.next_frame()

    def verify_start_state(self):
        assert self.ocr(0, 0, 0.25, 0.13, match="推荐活动")

    def run(self):
        entry = self.wait_ocr(0.085, 0.14, 0.21, 0.9, match="无音消除",
                              time_out=15, raise_if_not_found=True)
        assert len(entry) == 1
        self.click(entry[0], after_sleep=2)
        self.wait_ocr(0.55, 0.09, 0.99, 0.27, match="无音消除",
                      time_out=20, settle_time=1, raise_if_not_found=True)
        go = self.wait_ocr(0.76, 0.87, 0.99, 0.98, match="前往",
                           time_out=15, raise_if_not_found=True)
        assert len(go) == 1
        self.click(go[0], after_sleep=3)
        self.wait_ocr(0, 0, 0.4, 0.2, match=re.compile("无音消除"),
                      time_out=45, settle_time=1, raise_if_not_found=True)
        frame = self.next_frame()
        self.screenshot("playsage_tacet_stages")
        boxes = self.ocr(frame=frame)
        (self.artifact_directory / "stages.json").write_text(
            json.dumps([{"text": b.name, "x": b.x, "y": b.y} for b in boxes],
                       ensure_ascii=False, indent=2), encoding="utf-8"
        )
        assert boxes
