from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from src.core.logger.logger import logger
from src.modules.vectorization.application.dtos.search_query_dto import (
    SemanticSearchQueryDTO,
)
from src.modules.vectorization.application.dtos.search_result_dto import (
    SemanticSearchResultDTO,
)
from src.modules.vectorization.application.use_cases.semantic_search_use_case import (
    SemanticSearchUseCase,
)
from src.modules.vectorization.presentation.api.dependencies import (
    get_semantic_search_use_case,
)

router = APIRouter()


@router.post(
    "/semantic",
    summary="Semantic search across diarized YouTube videos",
    responses={
        500: {"description": "Semantic search failed"},
    },
)
def semantic_search(
    query: SemanticSearchQueryDTO,
    use_case: Annotated[SemanticSearchUseCase, Depends(get_semantic_search_use_case)],
) -> list[SemanticSearchResultDTO]:
    """Searches indexed transcript chunks by meaning using vector embeddings.

    Returns the top matching speech chunks with speaker attribution, timestamps,
    and direct YouTube deep links to the exact moment.
    """
    try:
        return use_case.execute(query)
    except Exception as exc:
        logger.error(f"Error during semantic search query '{query.query}': {exc}")
        raise HTTPException(
            status_code=500, detail=f"Semantic search failed: {exc}"
        ) from exc
