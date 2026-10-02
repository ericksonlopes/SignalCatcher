from fastapi import APIRouter

from src.modules.demograph.presentation.routes import (
    analyses,
    artifacts,
    catalog,
    extractions,
    health,
    runs,
    schema,
)

router = APIRouter(tags=["DemoGraph"])
for resource in (catalog, runs, artifacts, schema, health, extractions, analyses):
    router.include_router(resource.router)
