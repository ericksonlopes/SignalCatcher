from fastapi import APIRouter

from src.modules.demograph.presentation.routes import (
    artifacts,
    catalog,
    extractions,
    health,
    runs,
    schema,
)

router = APIRouter(tags=["DemoGraph"])
for resource in (catalog, runs, artifacts, schema, health, extractions):
    router.include_router(resource.router)
