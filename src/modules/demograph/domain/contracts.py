"""Public facade for the pipeline domain contracts."""

from src.modules.demograph.domain.entities.run import Run
from src.modules.demograph.domain.interfaces.catalog import Catalog
from src.modules.demograph.domain.interfaces.extractor import Extractor
from src.modules.demograph.domain.interfaces.loader import Loader
from src.modules.demograph.domain.rules.datasets import (
    DATASETS,
    DEPENDENCIES,
    TERMINAL,
    resolve_datasets,
)

__all__ = [
    "Run",
    "Catalog",
    "Extractor",
    "Loader",
    "DATASETS",
    "DEPENDENCIES",
    "TERMINAL",
    "resolve_datasets",
]
