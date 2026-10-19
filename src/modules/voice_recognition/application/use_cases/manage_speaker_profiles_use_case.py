import os
from datetime import datetime, timezone
from typing import Any

from src.core.config.settings import settings
from src.modules.voice_recognition.application.dtos.speaker_profile_dto import (
    BulkReviewSamplesRequestDTO,
    CreateSpeakerProfileDTO,
    ReviewSampleRequestDTO,
    SpeakerProfileResponseDTO,
    UpdateSpeakerProfileDTO,
    VoiceRecognitionStatsDTO,
    VoiceSampleResponseDTO,
)
from src.modules.voice_recognition.domain.entities.speaker_profile_entity import (
    SpeakerProfileEntity,
)
from src.modules.voice_recognition.domain.entities.voice_sample_entity import (
    VoiceSampleEntity,
)
from src.modules.voice_recognition.domain.enums.sample_review_status import (
    SampleReviewStatus,
)
from src.modules.voice_recognition.domain.interfaces import (
    ISpeakerRepository,
    IVoiceEmbeddingService,
)


def _compute_profile_strength(
    approved_count: int,
    total_speech_seconds: float,
    unique_sources_count: int,
) -> str:
    """Computes profile strength badge: 'weak', 'moderate', or 'strong'."""
    if approved_count >= 3 and total_speech_seconds >= 60.0 and unique_sources_count >= 2:
        return "strong"
    if approved_count >= 1 and total_speech_seconds >= 15.0:
        return "moderate"
    return "weak"


class ManageSpeakerProfilesUseCase:
    """Handles CRUD operations for speaker profiles, samples, review queue, and clips."""

    def __init__(
        self,
        speaker_repository: ISpeakerRepository,
        voice_embedding_service: IVoiceEmbeddingService,
    ) -> None:
        self.speaker_repository = speaker_repository
        self.voice_embedding_service = voice_embedding_service

    @staticmethod
    def _to_sample_dto(sample: VoiceSampleEntity) -> VoiceSampleResponseDTO:
        has_audio = bool(sample.clip_path and os.path.exists(sample.clip_path))
        return VoiceSampleResponseDTO(
            id=sample.id or "",
            speaker_id=sample.speaker_id,
            source_type=sample.source_type.value,
            source_id=sample.source_id,
            speaker_label=sample.speaker_label,
            start_time=sample.start_time,
            end_time=sample.end_time,
            duration_seconds=sample.duration_seconds,
            status=sample.status.value,
            clip_path=sample.clip_path,
            has_audio=has_audio,
            quality=sample.quality,
            reviewed_at=sample.reviewed_at,
            embedding_model=sample.embedding_model,
            metadata=sample.metadata,
            created_at=sample.created_at,
        )

    def _to_profile_dto(
        self,
        profile: SpeakerProfileEntity,
        include_samples: bool = False,
    ) -> SpeakerProfileResponseDTO:
        samples_dto = None
        strength = "weak"
        has_centroid = bool(profile.centroid)

        if profile.id:
            samples = self.speaker_repository.list_samples(speaker_id=profile.id)
            approved = [s for s in samples if s.status == SampleReviewStatus.APPROVED]
            total_speech = sum(float(s.duration_seconds or 0.0) for s in approved)
            unique_sources = len({s.source_id for s in approved if s.source_id})
            strength = _compute_profile_strength(len(approved), total_speech, unique_sources)

            if include_samples:
                samples_dto = [self._to_sample_dto(s) for s in samples]

        return SpeakerProfileResponseDTO(
            id=profile.id or "",
            name=profile.name,
            description=profile.description,
            avatar_url=profile.avatar_url,
            samples_count=profile.samples_count,
            pending_count=profile.pending_count,
            profile_strength=strength,
            has_centroid=has_centroid,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
            samples=samples_dto,
        )

    def create_profile(self, request: CreateSpeakerProfileDTO) -> SpeakerProfileResponseDTO:
        cleaned_name = request.name.strip()
        if not cleaned_name:
            raise ValueError("Speaker name cannot be empty.")

        entity = SpeakerProfileEntity(
            name=cleaned_name,
            description=request.description,
            avatar_url=request.avatar_url,
        )
        saved = self.speaker_repository.create_profile(entity)
        return self._to_profile_dto(saved, include_samples=True)

    def list_profiles(
        self,
        search: str | None = None,
        include_samples: bool = False,
    ) -> list[SpeakerProfileResponseDTO]:
        profiles = self.speaker_repository.list_profiles(search=search)
        return [self._to_profile_dto(p, include_samples=include_samples) for p in profiles]

    def get_profile(self, speaker_id: str) -> SpeakerProfileResponseDTO:
        profile = self.speaker_repository.get_profile(speaker_id)
        if not profile:
            raise ValueError(f"Speaker profile '{speaker_id}' not found.")
        return self._to_profile_dto(profile, include_samples=True)

    def update_profile(
        self,
        speaker_id: str,
        request: UpdateSpeakerProfileDTO,
    ) -> SpeakerProfileResponseDTO:
        updated = self.speaker_repository.update_profile(
            speaker_id=speaker_id,
            name=request.name,
            description=request.description,
            avatar_url=request.avatar_url,
        )
        if not updated:
            raise ValueError(f"Speaker profile '{speaker_id}' not found.")
        return self._to_profile_dto(updated, include_samples=True)

    def delete_profile(self, speaker_id: str) -> bool:
        deleted = self.speaker_repository.delete_profile(speaker_id)
        if not deleted:
            raise ValueError(f"Speaker profile '{speaker_id}' not found.")
        return True

    def delete_sample(self, sample_id: str) -> bool:
        deleted = self.speaker_repository.delete_sample(sample_id)
        if not deleted:
            raise ValueError(f"Voice sample '{sample_id}' not found.")
        return True

    def list_review_queue(
        self,
        speaker_id: str | None = None,
        status_filter: str = "PENDING_REVIEW",
    ) -> list[VoiceSampleResponseDTO]:
        """Lists samples for curation/review."""
        try:
            status = SampleReviewStatus(status_filter.upper())
        except ValueError:
            status = SampleReviewStatus.PENDING_REVIEW

        samples = self.speaker_repository.list_samples(
            speaker_id=speaker_id,
            status=status,
        )
        return [self._to_sample_dto(s) for s in samples]

    def review_sample(
        self,
        sample_id: str,
        request: ReviewSampleRequestDTO,
    ) -> VoiceSampleResponseDTO:
        """Approves, rejects, or adjusts crop timing for a sample candidate."""
        sample = self.speaker_repository.get_sample(sample_id)
        if not sample:
            raise ValueError(f"Voice sample '{sample_id}' not found.")

        target_status_str = request.status.strip().upper()
        if target_status_str not in {
            SampleReviewStatus.APPROVED.value,
            SampleReviewStatus.REJECTED.value,
        }:
            raise ValueError(
                f"Invalid status '{request.status}'. Must be 'APPROVED' or 'REJECTED'."
            )

        target_status = SampleReviewStatus(target_status_str)

        # Handle timing adjustment if requested
        if request.start_time is not None and request.end_time is not None:
            if request.end_time <= request.start_time:
                raise ValueError("end_time must be greater than start_time.")
            sample.start_time = round(request.start_time, 3)
            sample.end_time = round(request.end_time, 3)
            sample.duration_seconds = round(request.end_time - request.start_time, 3)

        # Re-extract neural embedding if approving and embedding_model is legacy/missing
        if target_status == SampleReviewStatus.APPROVED:
            if not sample.embedding_model or sample.embedding_model == "spectral-v1":
                clip_audio = sample.clip_path
                if clip_audio and os.path.exists(clip_audio):
                    try:
                        emb, model_name, quality = (
                            self.voice_embedding_service.extract_embedding_with_quality(
                                file_path=clip_audio,
                                segments=[{"start": 0.0, "end": 45.0}],
                            )
                        )
                        sample.embedding = emb
                        sample.embedding_model = model_name
                        sample.quality = {**(sample.quality or {}), **quality}
                    except Exception:
                        pass

        sample.status = target_status
        sample.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)

        updated = self.speaker_repository.update_sample(sample)
        return self._to_sample_dto(updated)

    def bulk_review_samples(
        self,
        request: BulkReviewSamplesRequestDTO,
    ) -> dict[str, Any]:
        """Approves or rejects multiple sample candidates in bulk."""
        processed = 0
        for sample_id in request.sample_ids:
            try:
                self.review_sample(
                    sample_id,
                    ReviewSampleRequestDTO(status=request.status),
                )
                processed += 1
            except Exception:
                continue
        return {
            "processed": processed,
            "total": len(request.sample_ids),
            "status": request.status.upper(),
        }

    def get_sample_audio_file(self, sample_id: str) -> str:
        """Returns the verified absolute path of a sample's WAV audio clip."""
        sample = self.speaker_repository.get_sample(sample_id)
        if not sample:
            raise ValueError(f"Voice sample '{sample_id}' not found.")
        if not sample.clip_path or not os.path.exists(sample.clip_path):
            raise FileNotFoundError(f"Audio file for sample '{sample_id}' was not found on disk.")

        # Path traversal guard
        clean_path = os.path.abspath(sample.clip_path)
        allowed_bases = [
            os.path.abspath(settings.VOICE_TRAINING_PATH or "."),
            os.path.abspath(settings.DOWNLOAD_YOUTUBE_PATH or "."),
        ]
        if not any(clean_path.startswith(base) for base in allowed_bases):
            raise PermissionError("Access to the requested audio path is not permitted.")
        return clean_path

    def get_stats(self) -> VoiceRecognitionStatsDTO:
        return VoiceRecognitionStatsDTO(
            total_profiles=self.speaker_repository.count_profiles(),
            total_samples=self.speaker_repository.count_samples(),
            pending_samples=self.speaker_repository.count_samples(
                status=SampleReviewStatus.PENDING_REVIEW
            ),
            approved_samples=self.speaker_repository.count_samples(
                status=SampleReviewStatus.APPROVED
            ),
            embedding_dimension=settings.VOICE_EMBEDDING_DIMENSION,
            default_similarity_threshold=settings.VOICE_SIMILARITY_THRESHOLD,
            worker_healthy=self.voice_embedding_service.health_check(),
        )
