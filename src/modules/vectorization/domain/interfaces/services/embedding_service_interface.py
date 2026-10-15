from abc import ABC, abstractmethod
from typing import Any


class IEmbeddingService(ABC):
    @abstractmethod
    def get_embeddings(
        self, texts: list[str], is_query: bool = False
    ) -> list[list[float]]:
        """Generates embedding vectors for a list of texts via TEI."""
        pass

    @abstractmethod
    def get_model_info(self) -> dict[str, Any]:
        """Fetches metadata of the model running on the TEI server."""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Verifies if the TEI server is reachable and healthy."""
        pass
