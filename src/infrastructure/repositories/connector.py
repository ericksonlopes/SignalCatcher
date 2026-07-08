from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.config.settings import settings

connect_args = {}

if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(settings.database_url, connect_args=connect_args)

Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

Base = declarative_base()


class ConnectorPostgres:
    def __init__(self):
        self.session = Session()

    def __enter__(self):
        return self.session

    def __exit__(self, *args, **kwargs):
        self.session.close()
