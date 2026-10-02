from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from src.modules.demograph.application.use_cases.delete_extraction import DeleteExtraction
from src.modules.demograph.presentation.dependencies.providers import get_deletion

router = APIRouter()


@router.delete("/extractions/{extraction_id}")
def delete_extraction(
    extraction_id: str, deletion: Annotated[DeleteExtraction, Depends(get_deletion)]
) -> dict[str, Any]:
    try:
        return deletion.execute(extraction_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            409, "Deletion unavailable. Wait for active runs or check artifact integrity."
        ) from exc
    except Exception as exc:
        raise HTTPException(
            503, "Deletion failed. Check storage and Neo4j, then retry deletion."
        ) from exc
