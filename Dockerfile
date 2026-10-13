FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    UV_COMPILE_BYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# Copy pre-built fast uv binary directly from official image (avoids pip install overhead)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# ffmpeg is required for yt-dlp stream merging. curl for container healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Create application user and working directory early
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --no-create-home appuser \
    && mkdir -p /app \
    && chown -R appuser:appuser /app

WORKDIR /app

# Switch to non-root appuser before installing packages.
# Files created by uv will automatically have correct permissions,
# completely eliminating the slow recursive chown on thousands of virtualenv files.
USER appuser

# Dependencies layer (cached unless pyproject.toml / uv.lock changes)
COPY --chown=appuser:appuser pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project

# Application code layer
COPY --chown=appuser:appuser src ./src
COPY --chown=appuser:appuser alembic ./alembic
COPY --chown=appuser:appuser alembic.ini main.py worker.py ./

RUN uv sync --frozen

# Migrations are owned by the dedicated Compose migrate service.
CMD ["/bin/sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
