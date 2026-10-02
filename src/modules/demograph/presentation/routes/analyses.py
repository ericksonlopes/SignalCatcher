from fastapi import APIRouter, BackgroundTasks, HTTPException

from src.modules.demograph.presentation.dependencies.catalog import CatalogDep
from src.modules.demograph.presentation.dependencies.pipeline import PipelineDep
from src.modules.demograph.presentation.dtos.analysis_request import AnalysisRequest

router = APIRouter()


@router.post("/analyses/party-similarity", status_code=202)
def analyze(
    body: AnalysisRequest, catalog: CatalogDep, pipeline: PipelineDep, background: BackgroundTasks
) -> dict[str, str]:
    parameters = {**body.model_dump(mode="json"), "datasets": []}
    try:
        run_id = catalog.create("analysis", parameters, status="running")
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    background.add_task(pipeline.execute, run_id)
    return {"id": run_id, "status": "running"}
