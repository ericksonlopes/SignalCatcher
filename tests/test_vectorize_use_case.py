import unittest
from unittest.mock import MagicMock

from src.modules.diarization.domain.entities.diarization_entity import DiarizationEntity
from src.modules.vectorization.application.use_cases.vectorize_diarization_use_case import (
    VectorizeDiarizationUseCase,
)
from src.modules.vectorization.domain.entities.vector_chunk_entity import (
    VectorChunkEntity,
)
from src.modules.vectorization.domain.enums.source_type import SourceType


class VectorizeDiarizationUseCaseTest(unittest.TestCase):
    def setUp(self):
        self.chunk_repo = MagicMock()
        self.embedding_service = MagicMock()
        self.chunking_strategy = MagicMock()
        self.diarization_repo = MagicMock()

        self.use_case = VectorizeDiarizationUseCase(
            chunk_repository=self.chunk_repo,
            embedding_service=self.embedding_service,
            chunking_strategy=self.chunking_strategy,
            diarization_repository=self.diarization_repo,
        )

    def test_task_not_found(self):
        self.diarization_repo.get_task.return_value = None
        with self.assertRaises(ValueError) as ctx:
            self.use_case.execute("non-existent-id")
        self.assertIn("not found", str(ctx.exception))

    def test_task_without_result_json(self):
        self.diarization_repo.get_task.return_value = DiarizationEntity(
            id="d1",
            file_path="test.mp4",
            result_json=None,
        )
        with self.assertRaises(ValueError) as ctx:
            self.use_case.execute("d1")
        self.assertIn("does not have result_json", str(ctx.exception))

    def test_successful_vectorization(self):
        self.diarization_repo.get_task.return_value = DiarizationEntity(
            id="d1",
            entity_id="video-123",
            file_path="test.mp4",
            result_json={"segments": [{"start": 0.0, "end": 10.0, "text": "Fala teste"}]},
        )
        self.chunking_strategy.create_chunks.return_value = [
            VectorChunkEntity(
                source_type=SourceType.YOUTUBE_TRANSCRIPT,
                source_id="d1",
                parent_id="video-123",
                chunk_index=0,
                text="Fala teste",
                metadata={"start_time": 0.0, "end_time": 10.0},
            )
        ]
        self.embedding_service.get_embeddings.return_value = [[0.1] * 768]

        status = self.use_case.execute("d1")

        self.assertTrue(status.indexed)
        self.assertEqual(status.chunks_count, 1)
        self.assertEqual(status.content_id, "video-123")
        self.chunk_repo.delete_by_source.assert_called_once_with(
            SourceType.YOUTUBE_TRANSCRIPT.value, "d1"
        )
        self.chunk_repo.save_chunks.assert_called_once()


if __name__ == "__main__":
    unittest.main()
