import unittest

from src.modules.vectorization.domain.enums.source_type import SourceType
from src.modules.vectorization.infrastructure.services.audio_transcript_chunking_strategy import (
    AudioTranscriptChunkingStrategy,
    format_timestamp,
)
from src.modules.vectorization.infrastructure.services.document_text_chunking_strategy import (
    DocumentTextChunkingStrategy,
)


class ChunkingStrategyTest(unittest.TestCase):
    def setUp(self):
        self.audio_strategy = AudioTranscriptChunkingStrategy(
            target_seconds=30.0,
            overlap_seconds=10.0,
            max_words_estimate=100,
        )
        self.doc_strategy = DocumentTextChunkingStrategy(
            chunk_size_words=10,
            chunk_overlap_words=2,
        )

    def test_format_timestamp(self):
        self.assertEqual(format_timestamp(0.0), "00:00")
        self.assertEqual(format_timestamp(65.0), "01:05")
        self.assertEqual(format_timestamp(3665.0), "01:01:05")

    def test_audio_empty_result_json(self):
        chunks = self.audio_strategy.create_chunks("d1", {})
        self.assertEqual(chunks, [])

        chunks = self.audio_strategy.create_chunks("d1", {"segments": []})
        self.assertEqual(chunks, [])

    def test_audio_chunking_and_metadata(self):
        result_json = {
            "segments": [
                {
                    "start": 0.0,
                    "end": 4.0,
                    "text": "Olá mundo.",
                    "speaker": "SPEAKER_00",
                },
                {
                    "start": 4.5,
                    "end": 8.0,
                    "text": "Olá a todos.",
                    "speaker": "SPEAKER_01",
                },
            ]
        }
        chunks = self.audio_strategy.create_chunks("d1", result_json, parent_id="v1")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].chunk_index, 0)
        self.assertEqual(chunks[0].source_type, SourceType.YOUTUBE_TRANSCRIPT)
        self.assertEqual(chunks[0].parent_id, "v1")
        self.assertEqual(chunks[0].start_time, 0.0)
        self.assertEqual(chunks[0].end_time, 8.0)
        self.assertIn("[SPEAKER_00]: Olá mundo.", chunks[0].text)
        self.assertIn("[SPEAKER_01]: Olá a todos.", chunks[0].text)
        self.assertIn("SPEAKER_00", chunks[0].speaker or "")
        self.assertIn("SPEAKER_01", chunks[0].speaker or "")

    def test_document_chunking(self):
        text = "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12"
        chunks = self.doc_strategy.create_chunks(
            source_id="doc1",
            content=text,
            parent_id="folderA",
            base_metadata={"file_name": "relatorio.txt", "author": "Analista"},
        )
        self.assertGreaterEqual(len(chunks), 2)
        self.assertEqual(chunks[0].source_type, SourceType.DOCUMENT)
        self.assertEqual(chunks[0].source_id, "doc1")
        self.assertEqual(chunks[0].parent_id, "folderA")
        self.assertEqual(chunks[0].metadata.get("file_name"), "relatorio.txt")


if __name__ == "__main__":
    unittest.main()
