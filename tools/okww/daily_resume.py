"""Resume core daily tasks after an observed failure of the optional nest pass."""
from daily import Task as DailyHarness


class Task(DailyHarness):
    skip_failed_nests = True
