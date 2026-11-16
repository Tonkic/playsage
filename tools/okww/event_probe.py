"""Inspect the currently observed seventh Tacet stage using native MCP APIs."""
import json
import re

from ok import BaseTask


class Task(BaseTask):
    def reset_to_start(self):
        self.next_frame()

    def verify_start_state(self):
        assert self.ocr(0, 0, .4, .13, match="无音消除")
        assert self.ocr(.75, .65, 1, .85, match=re.compile("除消除消除"))

    def run(self):
        cards = self.ocr(.75, .65, 1, .85, match=re.compile("除消除消除"))
        assert len(cards) == 1
        self.click(cards[0], after_sleep=2)
        self.wait_ocr(.5, .75, 1, 1, match=re.compile("开始挑战"),
                      time_out=20, settle_time=1, raise_if_not_found=True)
        frame = self.next_frame()
        self.screenshot("tacet_stage7_detail")
        (self.artifact_directory / "visible.json").write_text(json.dumps([
            {"text": b.name, "x": b.x, "y": b.y} for b in self.ocr(frame=frame)
        ], ensure_ascii=False, indent=2), encoding="utf-8")
