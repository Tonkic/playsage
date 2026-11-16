"""Enter the observed Tuantuan activity without selecting a challenge blindly."""
import json

from ok import BaseTask


class Task(BaseTask):
    def reset_to_start(self):
        self.next_frame()
        if self.ocr(0, 0, .3, .13, match="冒险目标"):
            self.send_key("esc", after_sleep=1)

    def verify_start_state(self):
        assert self.wait_ocr(.55, .09, .99, .27, match="团团勇者大乱斗", time_out=15)

    def run(self):
        entry = self.wait_ocr(.77, .88, .98, .95, match="前往", time_out=15)
        assert len(entry) == 1
        self.click(entry[0], after_sleep=3)
        frame = self.next_frame()
        self.screenshot("tuantuan_entry")
        boxes = self.ocr(frame=frame)
        assert boxes
        (self.artifact_directory / "visible.json").write_text(json.dumps([
            {"text": b.name, "x": b.x, "y": b.y} for b in boxes
        ], ensure_ascii=False, indent=2), encoding="utf-8")
