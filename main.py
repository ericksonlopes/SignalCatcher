import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.infrastructure.loggers.logger import logger
from src.infrastructure.repositories.connector import Base, engine
from src.presentation.schedules.scheduler_manager import start_scheduler

# Intercept default python logging to our custom logger
logging.basicConfig(handlers=[logger.get_intercept_handler()], level=logging.INFO, force=True)
for _log in ["uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"]:
    _logger = logging.getLogger(_log)
    _logger.handlers = [logger.get_intercept_handler()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting SignalCatcher API...")
    Base.metadata.create_all(engine)

    scheduler = start_scheduler()
    app.state.scheduler = scheduler

    yield

    logger.debug("Shutting down SignalCatcher scheduler...")
    scheduler.shutdown()


app = FastAPI(
    title="SignalCatcher API",
    description="API to manage content capture and monitoring (YouTube/RSS)",
    version="1.0.0",
    lifespan=lifespan
)

# Register routes
from src.presentation.api.routes import source_routes
from src.presentation.api.routes import scheduler_routes
from src.presentation.api.routes import content_routes

app.include_router(source_routes.router, prefix="/api/sources", tags=["Sources"])
app.include_router(scheduler_routes.router, prefix="/api/scheduler", tags=["Scheduler"])
app.include_router(content_routes.router, prefix="/api/content", tags=["Content"])


@app.get("/status", tags=["Health"])
def get_status():
    """Returns the API status (useful for Docker healthchecks)."""
    return {"status": "online", "message": "SignalCatcher is running"}


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
