from pathlib import Path

from src.core.config.settings import settings
from src.modules.demograph.infrastructure.catalog import SqlCatalog
from src.modules.demograph.infrastructure.graph import GraphLoader


def get_catalog() -> SqlCatalog:
    return SqlCatalog()


def get_graph() -> GraphLoader:
    return GraphLoader(
        SqlCatalog(),
        Path(settings.demograph_storage_path),
        settings.DEMOGRAPH_NEO4J_URI,
        settings.DEMOGRAPH_NEO4J_USER,
        settings.DEMOGRAPH_NEO4J_PASSWORD.get_secret_value()
        if settings.DEMOGRAPH_NEO4J_PASSWORD
        else None,
        settings.DEMOGRAPH_NEO4J_DATABASE,
    )
