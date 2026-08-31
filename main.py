import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware import Middleware

from src.core.config.settings import settings
from src.core.logger.logger import logger
from src.modules.youtube.presentation.schedules.scheduler_manager import start_scheduler

# Intercept default python logging to our custom logger
logging.basicConfig(handlers=[logger.get_intercept_handler()], level=logging.INFO, force=True)
for _log in ["uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"]:
    _logger = logging.getLogger(_log)
    _logger.handlers = [logger.get_intercept_handler()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting SignalCatcher API...")
    # The schema is owned by Alembic. `Base.metadata.create_all()` used to run here
    # too, which created tables outside the revision chain and let the real schema
    # drift from the migration history. Migrations are applied by the container
    # entrypoint (`alembic upgrade head`) before the server starts.
    scheduler = start_scheduler()
    app.state.scheduler = scheduler

    yield

    logger.debug("Shutting down SignalCatcher scheduler...")
    scheduler.shutdown()


middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        # No endpoint relies on cookies or HTTP auth, so credentials are not needed.
        # The previous combination of allow_origins=["*"] with allow_credentials=True is
        # forbidden by the CORS spec and rejected by browsers anyway.
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
]

app = FastAPI(
    title="SignalCatcher API",
    description="API to manage content capture and monitoring (YouTube/RSS)",
    version="1.0.0",
    lifespan=lifespan,
    middleware=middleware,
)

# Register routes
from src.modules.youtube.presentation.api.routes import youtube_router
from src.modules.diarization.presentation.api.routes import diarization_router

YOUTUBE_API_PREFIX = "/api/youtube"
app.include_router(youtube_router, prefix=YOUTUBE_API_PREFIX)

DIARIZATION_API_PREFIX = "/api/diarization"
app.include_router(diarization_router, prefix=DIARIZATION_API_PREFIX)


@app.get("/status", tags=["Health"])
def get_status():
    """Returns the API status (useful for Docker healthchecks)."""
    return {"status": "online", "message": "SignalCatcher is running"}


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
