from src.core.config.settings import settings
from src.modules.voice_recognition.application.dtos.speaker_profile_dto import (
    CreateSpeakerProfileDTO,
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
from src.modules.voice_recognition.domain.interfaces import (
    ISpeakerRepository,
    IVoiceEmbeddingService,
)


class ManageSpeakerProfilesUseCase:
    """Handles CRUD operations for speaker profiles, voice samples, and voice recognition stats."""

    def __init__(
        self,
        speaker_repository: ISpeakerRepository,
        voice_embedding_service: IVoiceEmbeddingService,
    ) -> None:
        self.speaker_repository = speaker_repository
        self.voice_embedding_service = voice_embedding_service

    @staticmethod
    def _to_sample_dto(sample: VoiceSampleEntity) -> VoiceSampleResponseDTO:
        return VoiceSampleResponseDTO(
            id=sample.id or "",
            speaker_id=sample.speaker_id,
            source_type=sample.source_type.value,
            source_id=sample.source_id,
            speaker_label=sample.speaker_label,
            start_time=sample.start_time,
            end_time=sample.end_time,
            duration_seconds=sample.duration_seconds,
            metadata=sample.metadata,
            created_at=sample.created_at,
        )

    def _to_profile_dto(
        self,
        profile: SpeakerProfileEntity,
        include_samples: bool = False,
    ) -> SpeakerProfileResponseDTO:
        samples_dto = None
        if include_samples and profile.id:
            samples = self.speaker_repository.list_samples(profile.id)
            samples_dto = [self._to_sample_dto(s) for s in samples]

        return SpeakerProfileResponseDTO(
            id=profile.id or "",
            name=profile.name,
            description=profile.description,
            avatar_url=profile.avatar_url,
            samples_count=profile.samples_count,
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

    def get_stats(self) -> VoiceRecognitionStatsDTO:
        return VoiceRecognitionStatsDTO(
            total_profiles=self.speaker_repository.count_profiles(),
            total_samples=self.speaker_repository.count_samples(),
            embedding_dimension=settings.VOICE_EMBEDDING_DIMENSION,
            default_similarity_threshold=settings.VOICE_SIMILARITY_THRESHOLD,
            worker_healthy=self.voice_embedding_service.health_check(),
        )
