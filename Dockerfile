FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip install uv

COPY pyproject.toml uv.lock README.md ./

RUN uv sync --frozen --no-install-project

COPY . .

RUN uv sync --frozen

ENV PATH="/app/.venv/bin:$PATH"

RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --no-create-home appuser \
    && chown -R appuser:appuser /app

USER appuser

# Roda as migrações do banco primeiro e depois inicia o servidor
CMD ["/bin/sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
