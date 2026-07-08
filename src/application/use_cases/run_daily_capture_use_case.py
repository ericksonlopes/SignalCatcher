from src.domain.interfaces.monitor_service import IMonitorTaskService


class RunDailyCaptureUseCase:
    def __init__(self, monitor_service: IMonitorTaskService):
        self.monitor_service = monitor_service

    def execute(self) -> None:
        self.monitor_service.daily_capture_routine()
