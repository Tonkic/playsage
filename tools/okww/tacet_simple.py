"""Delegate exactly the selected simple stage to the installed native task."""
import re

from ok import BaseTask
from src.task.TacetEliminationTask import TacetEliminationTask


class Task(BaseTask):
    def reset_to_start(self):
        self.event = self.get_task_by_class(TacetEliminationTask)
        self.event.prepare_event()

    def verify_start_state(self):
        assert self.event.ocr(.6, .05, 1, .2, match=re.compile("简单"))

    def run(self):
        self.event.run_simple_stage()
        self.next_frame()
        assert self.event.ocr(.2, .2, .8, .8, match=re.compile("挑战成功"))
        self.screenshot("simple_success_review")
