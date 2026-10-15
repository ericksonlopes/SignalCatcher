import unittest
from unittest.mock import MagicMock, patch

from src.modules.vectorization.infrastructure.services.tei_embedding_service import (
    TeiEmbeddingService,
)


class TeiEmbeddingServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = TeiEmbeddingService(
            base_url="http://fake-tei:8080",
            timeout_seconds=5.0,
            batch_size=2,
        )

    @patch("httpx.Client.post")
    def test_get_embeddings_with_e5_passage_prefix(self, mock_post):
        # Mock successful /embed response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [[0.1, 0.2], [0.3, 0.4]]
        mock_post.return_value = mock_response

        texts = ["Primeiro texto", "Segundo texto"]
        embeddings = self.service.get_embeddings(texts, is_query=False)

        self.assertEqual(len(embeddings), 2)
        # Verify prefix 'passage: ' was sent in payload
        call_kwargs = mock_post.call_args.kwargs
        sent_inputs = call_kwargs["json"]["inputs"]
        self.assertEqual(
            sent_inputs, ["passage: Primeiro texto", "passage: Segundo texto"]
        )

    @patch("httpx.Client.post")
    def test_get_embeddings_with_e5_query_prefix(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [[0.9, 0.8]]
        mock_post.return_value = mock_response

        texts = ["busca sobre inteligência artificial"]
        embeddings = self.service.get_embeddings(texts, is_query=True)

        self.assertEqual(len(embeddings), 1)
        call_kwargs = mock_post.call_args.kwargs
        sent_inputs = call_kwargs["json"]["inputs"]
        self.assertEqual(sent_inputs, ["query: busca sobre inteligência artificial"])

    @patch("httpx.Client.post")
    def test_fallback_to_openai_format(self, mock_post):
        # First call to /embed returns 404, second call to /v1/embeddings succeeds
        mock_404 = MagicMock()
        mock_404.status_code = 404

        mock_openai = MagicMock()
        mock_openai.status_code = 200
        mock_openai.json.return_value = {
            "data": [
                {"embedding": [0.5, 0.6]},
            ]
        }
        mock_post.side_effect = [mock_404, mock_openai]

        embeddings = self.service.get_embeddings(["Texto teste"], is_query=False)
        self.assertEqual(embeddings, [[0.5, 0.6]])


if __name__ == "__main__":
    unittest.main()
