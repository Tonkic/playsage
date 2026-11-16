"""Resume the visually verified stage-six simple board without restarting it."""
import re

from ok import BaseTask
from src.task.TacetEliminationTask import TacetEliminationTask


class Task(BaseTask):
    def reset_to_start(self):
        self.event = self.get_task_by_class(TacetEliminationTask)
        self.event.prepare_event()

    def verify_start_state(self):
        assert self.event.wait_until(self.event.is_board, time_out=15)
        assert self.event.ocr(0, .09, .4, .16, match=re.compile("4500"))

    def run(self):
        self.event.run_simple_stage(resume=True)
        self.next_frame()
        assert self.event.ocr(.2, .2, .8, .8, match=re.compile("挑战成功"))
        self.screenshot("simple_success_review")
