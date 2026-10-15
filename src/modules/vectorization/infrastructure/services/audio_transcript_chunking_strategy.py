import logging
from typing import Any

from src.core.config.settings import settings
from src.modules.vectorization.domain.entities.vector_chunk_entity import (
    VectorChunkEntity,
)
from src.modules.vectorization.domain.enums.source_type import SourceType
from src.modules.vectorization.domain.interfaces.services.chunking_strategy_interface import (
    IChunkingStrategy,
)

logger = logging.getLogger(__name__)


def format_timestamp(seconds: float) -> str:
    """Formats seconds into HH:MM:SS or MM:SS."""
    total_sec = int(round(seconds))
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    sec = total_sec % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{sec:02d}"
    return f"{minutes:02d}:{sec:02d}"


class AudioTranscriptChunkingStrategy(IChunkingStrategy):
    """Chunking strategy designed for WhisperX diarized audio.

    Groups consecutive spoken segments into coherent time windows (e.g., 45s)
    with a small sliding overlap (e.g., 10s), storing speaker information and
    timestamps in the polymorphic metadata payload.
    """

    def __init__(
        self,
        target_seconds: float | None = None,
        overlap_seconds: float | None = None,
        max_words_estimate: int | None = None,
    ) -> None:
        self.target_seconds = target_seconds or settings.CHUNK_TARGET_SECONDS
        self.overlap_seconds = overlap_seconds or settings.CHUNK_OVERLAP_SECONDS
        self.max_words = max_words_estimate or settings.CHUNK_MAX_TOKENS_ESTIMATE

    @property
    def supported_source_type(self) -> SourceType:
        return SourceType.YOUTUBE_TRANSCRIPT

    def create_chunks(
        self,
        source_id: str,
        content: Any,
        parent_id: str | None = None,
        base_metadata: dict[str, Any] | None = None,
    ) -> list[VectorChunkEntity]:
        segments = content.get("segments") if isinstance(content, dict) else None
        if not segments or not isinstance(segments, list):
            logger.warning("No segments found in transcript for source %s", source_id)
            return []

        chunks: list[VectorChunkEntity] = []
        n = len(segments)
        i = 0
        chunk_idx = 0

        while i < n:
            chunk_segments, j = self._collect_window_segments(segments, i, n)
            if not chunk_segments:
                i += 1
                continue

            chunk, c_end = self._create_chunk_entity(
                source_id=source_id,
                parent_id=parent_id,
                chunk_idx=chunk_idx,
                chunk_segments=chunk_segments,
                base_metadata=base_metadata,
            )
            chunks.append(chunk)
            chunk_idx += 1

            if j >= n:
                break

            i = self._calculate_next_start_index(segments, i, j, c_end)

        return chunks

    def _collect_window_segments(
        self,
        segments: list[dict[str, Any]],
        start_index: int,
        total_segments: int,
    ) -> tuple[list[dict[str, Any]], int]:
        chunk_segments: list[dict[str, Any]] = []
        chunk_start = float(segments[start_index].get("start", 0.0))
        words_count = 0
        j = start_index

        while j < total_segments:
            seg = segments[j]
            seg_text = str(seg.get("text", "")).strip()
            if seg_text:
                chunk_segments.append(seg)
                words_count += len(seg_text.split())

            seg_end = float(seg.get("end", chunk_start))
            duration = seg_end - chunk_start
            j += 1

            if duration >= self.target_seconds or words_count >= self.max_words:
                break

        return chunk_segments, j

    def _create_chunk_entity(
        self,
        source_id: str,
        parent_id: str | None,
        chunk_idx: int,
        chunk_segments: list[dict[str, Any]],
        base_metadata: dict[str, Any] | None,
    ) -> tuple[VectorChunkEntity, float]:
        formatted_text, speakers_list = self._format_chunk_dialogue(chunk_segments)
        c_start = float(chunk_segments[0].get("start", 0.0))
        c_end = float(chunk_segments[-1].get("end", c_start))
        speaker_str = ", ".join(speakers_list) if speakers_list else None

        meta: dict[str, Any] = {
            **(base_metadata or {}),
            "start_time": c_start,
            "end_time": c_end,
            "formatted_start_time": format_timestamp(c_start),
            "formatted_end_time": format_timestamp(c_end),
            "speaker": speaker_str,
            "speakers": speakers_list,
        }

        chunk = VectorChunkEntity(
            source_type=SourceType.YOUTUBE_TRANSCRIPT,
            source_id=source_id,
            parent_id=parent_id,
            chunk_index=chunk_idx,
            text=formatted_text,
            metadata=meta,
        )
        return chunk, c_end

    def _calculate_next_start_index(
        self,
        segments: list[dict[str, Any]],
        current_start: int,
        window_end_index: int,
        chunk_end_time: float,
    ) -> int:
        overlap_cutoff = chunk_end_time - self.overlap_seconds
        next_i = window_end_index
        for k in range(current_start + 1, window_end_index):
            if float(segments[k].get("start", 0.0)) >= overlap_cutoff:
                next_i = k
                break

        if next_i <= current_start:
            return current_start + 1
        return next_i

    def _format_chunk_dialogue(
        self, segments: list[dict[str, Any]]
    ) -> tuple[str, list[str]]:
        lines: list[str] = []
        unique_speakers: list[str] = []

        current_speaker: str | None = None
        current_texts: list[str] = []

        for seg in segments:
            speaker = seg.get("speaker") or "UNKNOWN"
            text = str(seg.get("text", "")).strip()
            if not text:
                continue

            if speaker not in unique_speakers:
                unique_speakers.append(speaker)

            if speaker == current_speaker:
                current_texts.append(text)
            else:
                if current_texts:
                    lines.append(f"[{current_speaker}]: {' '.join(current_texts)}")
                current_speaker = speaker
                current_texts = [text]

        if current_texts and current_speaker:
            lines.append(f"[{current_speaker}]: {' '.join(current_texts)}")

        return "\n".join(lines), unique_speakers
