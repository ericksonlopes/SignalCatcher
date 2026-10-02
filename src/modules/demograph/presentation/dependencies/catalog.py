from typing import Annotated

from fastapi import Depends

from src.modules.demograph.infrastructure.catalog import SqlCatalog
from src.modules.demograph.presentation.dependencies.providers import get_catalog

CatalogDep = Annotated[SqlCatalog, Depends(get_catalog)]
