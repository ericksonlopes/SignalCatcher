from typing import Any, Dict

from src.application.interfaces.ilogger import ILogger
from src.infrastructure.loggers.std_logger import InterceptHandler, StdLogger

LOG_FORMAT = "{asctime} | {levelname:<8} | {filepath}:{funcName}:{lineno} | {message} | {context}"


class Logger(ILogger):
    """
    Adapter que implementa a porta ILogger (Clean Architecture)
    """

    def __init__(self) -> None:
        self._logger = StdLogger(LOG_FORMAT)

    def debug(self, msg: str, context: Dict[str, Any] = None, *args, **kwargs) -> None:
        self._logger.debug(msg, context, *args, **kwargs)

    def info(self, msg: str, context: Dict[str, Any] = None, *args, **kwargs) -> None:
        self._logger.info(msg, context, *args, **kwargs)

    def warning(self, msg: str, context: Dict[str, Any] = None, *args, **kwargs) -> None:
        self._logger.warning(msg, context, *args, **kwargs)

    def error(self, msg: str, context: Dict[str, Any] = None, *args, **kwargs) -> None:
        self._logger.error(msg, context, *args, **kwargs)

    def critical(self, msg: str, context: Dict[str, Any] = None, *args, **kwargs) -> None:
        self._logger.critical(msg, context, *args, **kwargs)

    def get_intercept_handler(self):
        return InterceptHandler(self)


logger = Logger()
