from typing import Any, Protocol


class ILogger(Protocol):
    def debug(
        self, msg: str, context: dict[str, Any] | None = None, *args, **kwargs
    ) -> None: ...

    def info(
        self, msg: str, context: dict[str, Any] | None = None, *args, **kwargs
    ) -> None: ...

    def warning(
        self, msg: str, context: dict[str, Any] | None = None, *args, **kwargs
    ) -> None: ...

    def error(
        self, msg: str, context: dict[str, Any] | None = None, *args, **kwargs
    ) -> None: ...

    def critical(
        self, msg: str, context: dict[str, Any] | None = None, *args, **kwargs
    ) -> None: ...
