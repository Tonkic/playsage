"""Read earlier stage cards using the native event's existing drag helper."""
import json
import re

from ok import BaseTask
from src.task.MouseResetTask import MouseResetTask
from src.task.TacetEliminationTask import TacetEliminationTask


class Task(BaseTask):
    def reset_to_start(self):
        self.event = self.get_task_by_class(TacetEliminationTask)
        self.event.prepare_event()

    def verify_start_state(self):
        assert self.ocr(0, .45, 1, .9, match=re.compile("进行中|已完成"))
        assert (self.width, self.height) == (1920, 1080)

    def run(self):
        mouse = self.get_task_by_class(MouseResetTask)
        enabled = mouse._enabled
        mouse._enabled = False
        try:
            self.event.drag_relative((.7, .55), (.45, .55))
            self.wait_ocr(0, .45, 1, .9, match=re.compile("进行中|已完成"),
                          time_out=15, settle_time=1, raise_if_not_found=True)
            frame = self.next_frame()
            self.screenshot("tacet_earlier_stages")
            (self.artifact_directory / "cards.json").write_text(json.dumps([
                {"text": b.name, "x": b.x, "y": b.y} for b in self.ocr(frame=frame)
            ], ensure_ascii=False, indent=2), encoding="utf-8")
        finally:
            mouse._enabled = enabled
