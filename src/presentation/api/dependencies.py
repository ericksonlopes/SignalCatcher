from fastapi import Depends

from src.domain.interfaces.logger import ILogger
from src.application.use_cases.create_source_use_case import CreateSourceUseCase
from src.infrastructure.loggers.logger import logger as global_logger
from src.infrastructure.repositories.monitored_source_repository import MonitoredSourceRepository
from src.infrastructure.services.source_service import SourceService

def get_logger() -> ILogger:
    return global_logger


def get_monitored_source_repository(logger: ILogger = Depends(get_logger)) -> MonitoredSourceRepository:
    return MonitoredSourceRepository(logger=logger)


def get_source_service(
    repository: MonitoredSourceRepository = Depends(get_monitored_source_repository),
    logger: ILogger = Depends(get_logger)
) -> SourceService:
    return SourceService(repository=repository, logger=logger)


def get_create_source_use_case(
    service: SourceService = Depends(get_source_service),
    logger: ILogger = Depends(get_logger)
) -> CreateSourceUseCase:
    """
    Factory (Dependency Injection) that instantiates the Repository and the Concrete Infrastructure Service
    and injects them into the Application Use Case. The presentation layer (Routes) will only use this.
    """
    return CreateSourceUseCase(source_service=service, logger=logger)
