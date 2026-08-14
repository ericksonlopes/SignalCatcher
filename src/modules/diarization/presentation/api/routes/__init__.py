from fastapi import APIRouter
from src.modules.diarization.presentation.api.routes import diarization_route

diarization_router = APIRouter()

diarization_router.include_router(diarization_route.router, tags=["Diarization", "youtube"])
