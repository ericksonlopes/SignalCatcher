from typing import Protocol


class IMonitorTaskService(Protocol):
    def daily_capture_routine(self) -> int:
        """Executes the capture routine for all channels and returns the total number of new items found."""
        ...
