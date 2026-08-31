FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# ffmpeg is required, not optional: the download format requests
# bestvideo+bestaudio, and yt-dlp needs ffmpeg to merge the two streams. Without it the
# download failed at the merge step inside the container.
# curl is also what the compose healthcheck uses.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && pip install uv

COPY pyproject.toml uv.lock README.md ./

RUN uv sync --frozen --no-install-project

# Copy only what the application needs to run, instead of the whole build context.
# This avoids pulling in secrets or local data (.env, cookies.txt, credentials, the
# downloads directory) even if .dockerignore is ever incomplete.
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini main.py ./

RUN uv sync --frozen

ENV PATH="/app/.venv/bin:$PATH"

RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --no-create-home appuser \
    && chown -R appuser:appuser /app

USER appuser

# Roda as migrações do banco primeiro e depois inicia o servidor
CMD ["/bin/sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
