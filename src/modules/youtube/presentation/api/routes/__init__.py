from fastapi import APIRouter

from src.modules.youtube.presentation.api.routes import (
    channel_route,
    drive_oauth_route,
    playlist_route,
    storage_route,
    video_route,
)
from src.modules.youtube.presentation.schedules import scheduler_routes

youtube_router = APIRouter()
youtube_router.include_router(storage_route.router, tags=["YouTube", "Storage"])
youtube_router.include_router(drive_oauth_route.router, tags=["YouTube", "Storage"])

youtube_router.include_router(channel_route.router, tags=["YouTube", "channel"])
youtube_router.include_router(video_route.router, tags=["YouTube", "video"])
youtube_router.include_router(playlist_route.router, tags=["YouTube", "playlist"])
youtube_router.include_router(
    scheduler_routes.router, prefix="/scheduler", tags=["Scheduler", "YouTube"]
)
