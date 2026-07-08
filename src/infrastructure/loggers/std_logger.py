import logging
import sys
import json
from typing import Any, Dict, Union, Iterable, Set
from src.config.settings import settings

def _parse_allowed_levels(raw: Union[str, Iterable[str], None]) -> Set[int]:
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    allowed: Set[int] = set()
    if not raw:
        return allowed

    levels: Iterable[str]
    if isinstance(raw, str):
        levels = [item.strip() for item in raw.split(",") if item.strip()]
    else:
        levels = raw

    for level in levels:
        if isinstance(level, str):
            level = level.strip().upper()
        if level in level_map:
            allowed.add(level_map[level])
    return allowed

def get_allowed_levels() -> Set[int]:
    raw = settings.LIST_LOG_LEVELS
    return _parse_allowed_levels(raw)

class AllowedLevelsFilter(logging.Filter):
    def __init__(self, allowed_levels: Set[int]):
        super().__init__()
        self.allowed_levels = allowed_levels

    def filter(self, record: logging.LogRecord) -> bool:
        # Se nenhuma configuração foi definida (vazio/None), permite todos os logs
        if not self.allowed_levels:
            return True
        return record.levelno in self.allowed_levels

class CustomFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.filepath = record.pathname
        if not hasattr(record, "context"):
            record.context = ""
        elif isinstance(record.context, dict):
            record.context = json.dumps(record.context)
        return super().format(record)

class StdLogger:
    def __init__(self, log_format: str):
        self._logger = logging.getLogger("app_logger")
        self._logger.setLevel(logging.DEBUG)  # Always capture everything, handler decides what prints
        
        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = CustomFormatter(log_format, style="{")
            handler.setFormatter(formatter)
            
            allowed_levels = get_allowed_levels()
            handler.addFilter(AllowedLevelsFilter(allowed_levels))
            
            self._logger.addHandler(handler)
            self._logger.propagate = False


    def _log_with_context(self, level: int, msg: str, context: Dict[str, Any] = None, *args, **kwargs):
        """Método helper para injetar extra={'context': ...} no logger original."""
        extra = kwargs.pop("extra", {})
        extra["context"] = context if context else {}
        kwargs["extra"] = extra
        
        # Encontra dinamicamente o frame real que chamou o log, fora dos nossos wrappers
        import inspect
        frame = inspect.currentframe()
        depth = 1
        while frame:
            filename = frame.f_code.co_filename
            # Ignora os arquivos de logging do python e nossos wrappers
            if "logging" not in filename and "loggers" not in filename.replace("\\", "/"):
                break
            frame = frame.f_back
            depth += 1
            
        self._logger.log(level, msg, *args, stacklevel=depth, **kwargs)

    def debug(self, msg: str, context: Dict[str, Any] = None, *args, **kwargs):
        self._log_with_context(logging.DEBUG, msg, context, *args, **kwargs)

    def info(self, msg: str, context: Dict[str, Any] = None, *args, **kwargs):
        self._log_with_context(logging.INFO, msg, context, *args, **kwargs)

    def warning(self, msg: str, context: Dict[str, Any] = None, *args, **kwargs):
        self._log_with_context(logging.WARNING, msg, context, *args, **kwargs)

    def error(self, msg: str, context: Dict[str, Any] = None, *args, **kwargs):
        self._log_with_context(logging.ERROR, msg, context, *args, **kwargs)
        
    def critical(self, msg: str, context: Dict[str, Any] = None, *args, **kwargs):
        self._log_with_context(logging.CRITICAL, msg, context, *args, **kwargs)

class InterceptHandler(logging.Handler):
    """
    Intercepta logs de outras bibliotecas (uvicorn, fastapi, etc) e joga pro nosso logger customizado.
    """
    def __init__(self, custom_logger):
        super().__init__()
        self.custom_logger = custom_logger

    def emit(self, record: logging.LogRecord):
        # Injeta o contexto se não existir
        if not hasattr(record, "context"):
            record.context = {"exc_info": record.exc_text} if record.exc_info else {}
            
        # Repassa o LogRecord original com a linha e arquivo originais intactos
        # self.custom_logger._logger._logger aponta para o logging.Logger real ("app_logger")
        self.custom_logger._logger._logger.handle(record)

