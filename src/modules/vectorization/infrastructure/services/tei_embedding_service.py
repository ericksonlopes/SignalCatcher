import logging
from typing import Any

import httpx

from src.core.config.settings import settings
from src.modules.vectorization.domain.interfaces.services.embedding_service_interface import (
    IEmbeddingService,
)

logger = logging.getLogger(__name__)


class TeiEmbeddingService(IEmbeddingService):
    """Client for Hugging Face Text Embeddings Inference (TEI) service running in Portainer."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        batch_size: int | None = None,
    ) -> None:
        self.base_url = (base_url or settings.TEI_API_URL).rstrip("/")
        self.timeout = timeout_seconds or settings.TEI_TIMEOUT_SECONDS
        self.batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE

    def get_embeddings(self, texts: list[str], is_query: bool = False) -> list[list[float]]:
        if not texts:
            return []

        # Model e5 expects 'query: ' for search and 'passage: ' for document passages
        prefix = "query: " if is_query else "passage: "
        formatted_texts: list[str] = [
            (
                f"{prefix}{t.strip()}"
                if not t.strip().startswith(("passage: ", "query: "))
                else t.strip()
            )
            for t in texts
        ]

        all_embeddings: list[list[float]] = []

        with httpx.Client(timeout=self.timeout) as client:
            for i in range(0, len(formatted_texts), self.batch_size):
                batch = formatted_texts[i : i + self.batch_size]
                embeddings = self._embed_batch(client, batch)
                all_embeddings.extend(embeddings)

        return all_embeddings

    def _embed_batch(self, client: httpx.Client, batch: list[str]) -> list[list[float]]:
        # 1. Try native TEI endpoint /embed
        embed_url = f"{self.base_url}/embed"
        try:
            response = client.post(
                embed_url,
                json={"inputs": batch, "truncate": True},
                headers={"Content-Type": "application/json"},
            )
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    return data
            elif response.status_code != 404:
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(
                "TEI native /embed call failed with %s; falling back to /v1/embeddings",
                exc,
            )

        # 2. Fallback to OpenAI-compatible /v1/embeddings
        openai_url = f"{self.base_url}/v1/embeddings"
        response = client.post(
            openai_url,
            json={"input": batch},
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        data = response.json()
        items = data.get("data", [])
        return [item["embedding"] for item in items]

    def get_model_info(self) -> dict[str, Any]:
        with httpx.Client(timeout=5.0) as client:
            res = client.get(f"{self.base_url}/info")
            res.raise_for_status()
            return res.json()

    def health_check(self) -> bool:
        try:
            with httpx.Client(timeout=3.0) as client:
                res = client.get(f"{self.base_url}/health")
                return res.status_code in (200, 204)
        except Exception:
            return False
