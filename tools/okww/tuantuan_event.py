"""Navigate from the reviewed Tacet selector to the Tuantuan event page."""
import json
import re

from ok import BaseTask


class Task(BaseTask):
    def reset_to_start(self):
        self.next_frame()
        if self.ocr(0, 0, .25, .13, match="无音消除"):
            assert self.ocr(0, .45, 1, .9, match=re.compile("进行中|已完成"))
            self.send_key("esc", after_sleep=2)

    def verify_start_state(self):
        assert self.wait_ocr(0, 0, .25, .13, match="推荐活动", time_out=20)

    def run(self):
        title = "团团勇者大乱斗"
        entries = self.wait_ocr(.085, .14, .21, .9, match=title, time_out=15)
        assert len(entries) == 1
        self.click(entries[0], after_sleep=2)
        self.wait_ocr(.55, .09, .99, .27, match=title,
                      time_out=20, raise_if_not_found=True)
        frame = self.next_frame()
        self.screenshot("tuantuan_event")
        (self.artifact_directory / "visible.json").write_text(json.dumps([
            {"text": b.name, "x": b.x, "y": b.y} for b in self.ocr(frame=frame)
        ], ensure_ascii=False, indent=2), encoding="utf-8")
