from src.modules.vectorization.presentation.api.routes.search_route import (
    router as search_router,
)
from src.modules.vectorization.presentation.api.routes.vectorization_route import (
    router as vectorization_router,
)

__all__ = [
    "search_router",
    "vectorization_router",
]
