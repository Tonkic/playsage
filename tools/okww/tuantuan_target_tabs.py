"""Inspect the three already observed objective categories."""
import json

from ok import BaseTask


class Task(BaseTask):
    def reset_to_start(self):
        self.next_frame()

    def verify_start_state(self):
        assert self.ocr(0, 0, .3, .13, match="冒险目标")

    def run(self):
        for title in ["挑战", "角色", "其他"]:
            entry = self.wait_ocr(.5, .1, .95, .2, match=title, time_out=10)
            assert len(entry) == 1
            self.click(entry[0], after_sleep=1)
            frame = self.next_frame()
            boxes = self.ocr(frame=frame)
            assert boxes
            self.screenshot("tuantuan_targets_" + title)
            (self.artifact_directory / (title + ".json")).write_text(json.dumps([
                {"text": b.name, "x": b.x, "y": b.y} for b in boxes
            ], ensure_ascii=False, indent=2), encoding="utf-8")
