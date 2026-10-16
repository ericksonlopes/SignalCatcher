import copy
import logging
from typing import Any

from src.modules.diarization.domain.interfaces.repositories.diarization_repository import (
    IDiarizationRepository,
)
from src.modules.voice_recognition.application.dtos.enroll_speaker_dto import (
    EnrollFromDiarizationDTO,
    EnrollResponseDTO,
)
from src.modules.voice_recognition.domain.entities.speaker_profile_entity import (
    SpeakerProfileEntity,
)
from src.modules.voice_recognition.domain.entities.voice_sample_entity import (
    VoiceSampleEntity,
)
from src.modules.voice_recognition.domain.enums.voice_source_type import VoiceSourceType
from src.modules.voice_recognition.domain.interfaces import (
    ISpeakerRepository,
    IVoiceEmbeddingService,
)

logger = logging.getLogger(__name__)


def apply_speaker_mapping_to_result_json(
    result_json: dict[str, Any],
    target_label: str,
    speaker_name: str,
    speaker_id: str | None = None,
    similarity_score: float = 1.0,
) -> dict[str, Any]:
    """Replaces `target_label` with `speaker_name` in a diarization `result_json`,
    preserving `original_speaker` and recording `speaker_mappings`."""
    updated = copy.deepcopy(result_json)
    segments = updated.get("segments", [])
    original_key = target_label

    for seg in segments:
        curr_spk = seg.get("speaker", "UNKNOWN")
        orig_spk = seg.get("original_speaker", curr_spk)
        if curr_spk == target_label or orig_spk == target_label:
            seg["original_speaker"] = orig_spk
            seg["speaker"] = speaker_name
            if speaker_id:
                seg["speaker_id"] = speaker_id
            original_key = orig_spk

    # Rebuild speakers list in order of appearance
    seen_speakers: list[str] = []
    for seg in segments:
        spk = seg.get("speaker")
        if spk and spk not in seen_speakers:
            seen_speakers.append(spk)
    updated["speakers"] = seen_speakers

    mappings = dict(updated.get("speaker_mappings") or {})
    mappings[original_key] = {
        "original_speaker": original_key,
        "speaker_id": speaker_id,
        "speaker_name": speaker_name,
        "similarity_score": round(float(similarity_score), 4),
    }
    updated["speaker_mappings"] = mappings
    return updated


class EnrollSpeakerUseCase:
    """Enrolls a speaker voiceprint from a completed diarization or from an uploaded file."""

    def __init__(
        self,
        speaker_repository: ISpeakerRepository,
        voice_embedding_service: IVoiceEmbeddingService,
        diarization_repository: IDiarizationRepository,
    ) -> None:
        self.speaker_repository = speaker_repository
        self.voice_embedding_service = voice_embedding_service
        self.diarization_repository = diarization_repository

    def _resolve_or_create_profile(
        self,
        speaker_id: str | None,
        speaker_name: str | None,
        description: str | None = None,
    ) -> SpeakerProfileEntity:
        if speaker_id:
            profile = self.speaker_repository.get_profile(speaker_id)
            if not profile:
                raise ValueError(f"Speaker profile '{speaker_id}' not found.")
            return profile

        if not speaker_name or not speaker_name.strip():
            raise ValueError("Either speaker_id or speaker_name must be provided.")

        cleaned_name = speaker_name.strip()
        existing = self.speaker_repository.get_profile_by_name(cleaned_name)
        if existing:
            return existing

        return self.speaker_repository.create_profile(
            SpeakerProfileEntity(name=cleaned_name, description=description)
        )

    def enroll_from_diarization(self, request: EnrollFromDiarizationDTO) -> EnrollResponseDTO:
        task = self.diarization_repository.get_task(request.diarization_id)
        if not task:
            raise ValueError(f"Diarization task '{request.diarization_id}' not found.")

        if not task.result_json or not isinstance(task.result_json, dict):
            raise ValueError(
                f"Diarization '{request.diarization_id}' has no completed transcript result_json."
            )

        raw_segments = task.result_json.get("segments", [])
        matching_segments = [
            seg
            for seg in raw_segments
            if seg.get("speaker") == request.speaker_label
            or seg.get("original_speaker") == request.speaker_label
        ]

        if not matching_segments:
            raise ValueError(
                f"No segments found for speaker '{request.speaker_label}' "
                f"in diarization '{request.diarization_id}'."
            )

        profile = self._resolve_or_create_profile(
            speaker_id=request.speaker_id,
            speaker_name=request.speaker_name,
            description=request.description,
        )

        embedding = self.voice_embedding_service.extract_embedding_from_segments(
            file_path=task.file_path,
            segments=matching_segments,
        )

        start_time = min(float(s.get("start", 0.0)) for s in matching_segments)
        end_time = max(float(s.get("end", 0.0)) for s in matching_segments)
        speech_duration = sum(
            max(0.0, float(s.get("end", 0.0)) - float(s.get("start", 0.0)))
            for s in matching_segments
        )

        sample = VoiceSampleEntity(
            speaker_id=profile.id or "",
            source_type=VoiceSourceType.DIARIZATION_SEGMENT,
            source_id=task.id,
            speaker_label=request.speaker_label,
            start_time=round(start_time, 3),
            end_time=round(end_time, 3),
            duration_seconds=round(speech_duration, 3),
            metadata={
                "entity_id": task.entity_id,
                "entity_type": task.entity_type,
                "segments_count": len(matching_segments),
                "sample_text": " ".join(
                    str(s.get("text", "")).strip() for s in matching_segments[:3]
                )[:240],
            },
            embedding=embedding,
        )
        saved_sample = self.speaker_repository.add_sample(sample)

        applied = False
        if request.apply_to_diarization and task.id:
            updated_json = apply_speaker_mapping_to_result_json(
                result_json=task.result_json,
                target_label=request.speaker_label,
                speaker_name=profile.name,
                speaker_id=profile.id,
                similarity_score=1.0,
            )
            self.diarization_repository.update_result_json(task.id, updated_json)
            applied = True

        updated_profile = self.speaker_repository.get_profile(profile.id or "") or profile

        logger.info(
            "Enrolled speaker '%s' (id=%s) from diarization %s speaker %s (%d segments, %.1fs)",
            profile.name,
            profile.id,
            task.id,
            request.speaker_label,
            len(matching_segments),
            speech_duration,
        )

        return EnrollResponseDTO(
            speaker_id=profile.id or "",
            speaker_name=profile.name,
            sample_id=saved_sample.id or "",
            source_type=VoiceSourceType.DIARIZATION_SEGMENT.value,
            source_id=task.id,
            speaker_label=request.speaker_label,
            segments_used=len(matching_segments),
            speech_duration_seconds=round(speech_duration, 2),
            applied_to_diarization=applied,
            samples_count=updated_profile.samples_count,
        )

    def enroll_from_upload(
        self,
        audio_bytes: bytes,
        filename: str,
        speaker_id: str | None = None,
        speaker_name: str | None = None,
        description: str | None = None,
    ) -> EnrollResponseDTO:
        profile = self._resolve_or_create_profile(
            speaker_id=speaker_id,
            speaker_name=speaker_name,
            description=description,
        )

        embedding = self.voice_embedding_service.extract_embedding_from_bytes(
            audio_bytes=audio_bytes,
            filename=filename,
        )

        sample = VoiceSampleEntity(
            speaker_id=profile.id or "",
            source_type=VoiceSourceType.AUDIO_UPLOAD,
            source_id=filename,
            speaker_label="UPLOAD",
            metadata={"filename": filename, "size_bytes": len(audio_bytes)},
            embedding=embedding,
        )
        saved_sample = self.speaker_repository.add_sample(sample)
        updated_profile = self.speaker_repository.get_profile(profile.id or "") or profile

        return EnrollResponseDTO(
            speaker_id=profile.id or "",
            speaker_name=profile.name,
            sample_id=saved_sample.id or "",
            source_type=VoiceSourceType.AUDIO_UPLOAD.value,
            source_id=filename,
            speaker_label="UPLOAD",
            segments_used=1,
            speech_duration_seconds=0.0,
            applied_to_diarization=False,
            samples_count=updated_profile.samples_count,
        )
