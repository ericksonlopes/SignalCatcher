import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from src.core.api.health import readiness
from src.core.api.metrics import router as metrics_router
from src.core.api.security import require_admin
from src.core.config.settings import settings
from src.core.logger.logger import logger
from src.modules.diarization.presentation.api.routes import diarization_router
from src.modules.youtube.presentation.api.routes import youtube_router

logging.basicConfig(handlers=[logger.get_intercept_handler()], level=logging.INFO, force=True)
for name in ["uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"]:
    logging.getLogger(name).handlers = [logger.get_intercept_handler()]

app = FastAPI(
    title="SignalCatcher API",
    description="Content capture, monitoring and diarization management",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)
app.include_router(youtube_router, prefix="/api/youtube", dependencies=[Depends(require_admin)])
app.include_router(
    diarization_router, prefix="/api/diarization", dependencies=[Depends(require_admin)]
)
app.include_router(metrics_router)


@app.get("/status", tags=["Health"])
def get_status():
    return {"status": "online", "message": "SignalCatcher is running"}


@app.get("/ready", tags=["Health"])
def get_readiness():
    checks = readiness()
    ready = all(checks.values())
    return JSONResponse(
        {"status": "ready" if ready else "unavailable", "checks": checks},
        status_code=200 if ready else 503,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
