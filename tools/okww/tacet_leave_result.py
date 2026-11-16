"""Leave a visually verified success result and return to the stage selector."""
import json
import re

from ok import BaseTask


class Task(BaseTask):
    def reset_to_start(self):
        self.next_frame()

    def verify_start_state(self):
        assert (self.ocr(.2, .2, .8, .8, match=re.compile("挑战成功"))
                or self.ocr(.6, .05, 1, .2, match=re.compile("除消除消除")))

    def run(self):
        button = self.ocr(.25, .8, .75, .96, match="退出关卡")
        if button:
            assert len(button) == 1
            self.click(button[0], after_sleep=2)
        # Completing simple automatically selects the newly unlocked hard tab.
        self.wait_ocr(0, .15, .25, .3, match="简单",
                      time_out=20, raise_if_not_found=True)
        self.screenshot("simple_claimed_detail")
        self.send_key("esc", after_sleep=2)
        self.wait_ocr(0, .45, 1, .9, match=re.compile("进行中|已完成"),
                      time_out=20, raise_if_not_found=True)
        frame = self.next_frame()
        self.screenshot("simple_stage_selector")
        (self.artifact_directory / "visible.json").write_text(json.dumps([
            {"text": b.name, "x": b.x, "y": b.y} for b in self.ocr(frame=frame)
        ], ensure_ascii=False, indent=2), encoding="utf-8")
