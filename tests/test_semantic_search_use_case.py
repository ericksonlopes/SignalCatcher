import unittest
from unittest.mock import MagicMock

from src.modules.vectorization.application.dtos.search_query_dto import (
    SemanticSearchQueryDTO,
)
from src.modules.vectorization.application.use_cases.semantic_search_use_case import (
    SemanticSearchUseCase,
)
from src.modules.vectorization.domain.entities.vector_chunk_entity import (
    VectorChunkEntity,
)
from src.modules.vectorization.domain.enums.source_type import SourceType
from src.modules.youtube.domain.entities.youtube_content_entity import (
    YoutubeContentEntity,
)


class SemanticSearchUseCaseTest(unittest.TestCase):
    def setUp(self):
        self.chunk_repo = MagicMock()
        self.embedding_service = MagicMock()
        self.youtube_contents = MagicMock()

        self.use_case = SemanticSearchUseCase(
            chunk_repository=self.chunk_repo,
            embedding_service=self.embedding_service,
            youtube_contents=self.youtube_contents,
        )

    def test_semantic_search_enrichment(self):
        # 1. Query vector
        self.embedding_service.get_embeddings.return_value = [[0.2] * 768]

        # 2. Similarity search match
        matched_chunk = VectorChunkEntity(
            id="c1",
            source_type=SourceType.YOUTUBE_TRANSCRIPT,
            source_id="d1",
            parent_id="ext-video-1",
            chunk_index=0,
            text="[SPEAKER_00]: Falando de inteligência artificial.",
            metadata={
                "start_time": 125.0,
                "end_time": 160.0,
                "speaker": "SPEAKER_00",
            },
        )
        self.chunk_repo.similarity_search.return_value = [(matched_chunk, 0.885)]

        # 3. YouTube content metadata
        content_mock = MagicMock(spec=YoutubeContentEntity)
        content_mock.title = "Episódio 42 - IA no Brasil"
        content_mock.origin = "Podcast Tech"
        content_mock.thumbnail = "https://thumb.url/1.jpg"

        self.youtube_contents.get_many_by_external_ids.return_value = {
            "ext-video-1": content_mock
        }

        query = SemanticSearchQueryDTO(query="inteligência artificial", limit=5)
        results = self.use_case.execute(query)

        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertEqual(res.chunk_id, "c1")
        self.assertEqual(res.source_type, SourceType.YOUTUBE_TRANSCRIPT.value)
        self.assertEqual(res.title, "Episódio 42 - IA no Brasil")
        self.assertEqual(res.subtitle, "Podcast Tech")
        self.assertEqual(res.formatted_start_time, "02:05")
        self.assertEqual(res.formatted_end_time, "02:40")
        self.assertEqual(res.similarity_score, 0.885)
        self.assertEqual(
            res.deep_link,
            "https://www.youtube.com/watch?v=ext-video-1&t=125s",
        )


if __name__ == "__main__":
    unittest.main()
