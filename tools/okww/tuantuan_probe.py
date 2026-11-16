"""One reviewed Tuantuan UI transition, followed by native observation."""
import json
import re

from ok import BaseTask


class Task(BaseTask):
    def reset_to_start(self):
        self.next_frame()

    def verify_start_state(self):
        assert (self.width, self.height) == (1920, 1080)
        assert self.ocr(.29, .09, .53, .18, match=re.compile("晶块"))

    def run(self):
        self.click(.55, .8, after_sleep=.5)
        self.next_frame()
        assert not self.ocr(.29, .09, .53, .18, match=re.compile("晶块"))
        self.click(.676, .394, after_sleep=1)
        self.wait_ocr(0, 0, 1, 1, match=re.compile("."), time_out=20,
                      settle_time=1, raise_if_not_found=True)
        frame = self.next_frame()
        boxes = self.ocr(frame=frame)
        assert boxes
        self.screenshot("tuantuan_probe")
        (self.artifact_directory / "visible.json").write_text(json.dumps([
            {"text": b.name, "x": b.x, "y": b.y} for b in boxes
        ], ensure_ascii=False, indent=2), encoding="utf-8")
