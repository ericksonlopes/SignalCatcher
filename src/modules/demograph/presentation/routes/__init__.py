from fastapi import APIRouter

from src.modules.demograph.presentation.routes import artifacts, catalog, health, runs, schema

router = APIRouter(tags=["DemoGraph"])
for resource in (catalog, runs, artifacts, schema, health):
    router.include_router(resource.router)
