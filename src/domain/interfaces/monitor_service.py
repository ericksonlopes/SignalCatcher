from typing import Protocol


class IMonitorTaskService(Protocol):
    def daily_capture_routine(self) -> None:
        """Executes the capture routine for all channels."""
        ...
