from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SqlAlchemySession
from sqlalchemy.orm import declarative_base, sessionmaker

from src.core.config.settings import settings

connect_args: dict[str, Any] = {}

if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(settings.database_url, connect_args=connect_args)

# Session factory. Kept under this name because it is imported as such across the
# project; `SqlAlchemyUnitOfWork` takes it as its default session factory.
Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

Base = declarative_base()


class ConnectorPostgres:
    """Standalone session helper kept for the one-off maintenance scripts in `script/`.

    The application itself no longer uses this. Repositories now receive their session
    from a `SqlAlchemyUnitOfWork`, so the transaction boundary belongs to the business
    operation instead of to each individual repository call.
    """

    def __init__(self) -> None:
        self.session: SqlAlchemySession = Session()

    def __enter__(self) -> SqlAlchemySession:
        return self.session

    def __exit__(self, *args: Any, **kwargs: Any) -> None:
        self.session.close()
