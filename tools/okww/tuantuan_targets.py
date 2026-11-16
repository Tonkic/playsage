"""Open the observed adventure-objective panel for rule inspection."""
import json

from ok import BaseTask


class Task(BaseTask):
    def reset_to_start(self):
        self.next_frame()

    def verify_start_state(self):
        assert self.ocr(.55, .09, .99, .27, match="团团勇者大乱斗")
        assert (self.width, self.height) == (1920, 1080)

    def run(self):
        button = self.wait_ocr(.25, .82, .42, .94, match="冒险目标", time_out=15)
        assert len(button) == 1
        self.click(button[0], after_sleep=2)
        self.wait_ocr(0, 0, .5, .15, match="冒险目标", time_out=20,
                      raise_if_not_found=True)
        frame = self.next_frame()
        self.screenshot("tuantuan_objectives")
        (self.artifact_directory / "visible.json").write_text(json.dumps([
            {"text": b.name, "x": b.x, "y": b.y} for b in self.ocr(frame=frame)
        ], ensure_ascii=False, indent=2), encoding="utf-8")
