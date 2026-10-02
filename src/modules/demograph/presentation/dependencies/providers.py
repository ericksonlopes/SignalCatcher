from pathlib import Path

from src.core.config.settings import settings
from src.modules.demograph.application.use_cases.delete_extraction import DeleteExtraction
from src.modules.demograph.application.use_cases.pipeline import Pipeline
from src.modules.demograph.infrastructure.catalog import SqlCatalog
from src.modules.demograph.infrastructure.extraction import ChamberExtractor
from src.modules.demograph.infrastructure.graph import GraphLoader
from src.modules.demograph.infrastructure.graph.party_similarity import PartySimilarity
from src.modules.demograph.infrastructure.storage.deletion import ExtractionFiles


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


def get_pipeline() -> Pipeline:
    catalog = SqlCatalog()
    root = Path(settings.demograph_storage_path)
    graph = get_graph()
    return Pipeline(
        catalog,
        ChamberExtractor(catalog, root, max_workers=settings.DEMOGRAPH_HTTP_CONCURRENCY),
        graph,
        PartySimilarity(graph),
    )


def get_deletion() -> DeleteExtraction:
    return DeleteExtraction(
        SqlCatalog(), get_graph(), ExtractionFiles(Path(settings.demograph_storage_path))
    )
