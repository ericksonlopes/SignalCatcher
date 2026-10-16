import uuid

from src.modules.voice_recognition.domain.entities.speaker_profile_entity import (
    SpeakerProfileEntity,
)
from src.modules.voice_recognition.domain.entities.voice_sample_entity import (
    VoiceSampleEntity,
)
from src.modules.voice_recognition.domain.enums.voice_source_type import VoiceSourceType
from src.modules.voice_recognition.infrastructure.repositories.models.speaker_profile_model import (
    SpeakerProfileModel,
    VoiceSampleModel,
)


class SpeakerMapper:
    @staticmethod
    def profile_to_entity(model: SpeakerProfileModel) -> SpeakerProfileEntity:
        return SpeakerProfileEntity(
            id=model.id,
            name=model.name,
            description=model.description,
            avatar_url=model.avatar_url,
            samples_count=int(model.samples_count or 0),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def profile_to_model(entity: SpeakerProfileEntity) -> SpeakerProfileModel:
        return SpeakerProfileModel(
            id=entity.id or str(uuid.uuid4()),
            name=entity.name.strip(),
            description=entity.description,
            avatar_url=entity.avatar_url,
            samples_count=entity.samples_count,
        )

    @staticmethod
    def sample_to_entity(model: VoiceSampleModel) -> VoiceSampleEntity:
        raw_embedding: list[float] | None = getattr(model, "embedding", None)
        embedding_list = (
            [float(x) for x in raw_embedding] if raw_embedding is not None else None
        )
        try:
            source_type = VoiceSourceType(model.source_type)
        except ValueError:
            source_type = VoiceSourceType.DIARIZATION_SEGMENT

        return VoiceSampleEntity(
            id=model.id,
            speaker_id=model.speaker_id,
            source_type=source_type,
            source_id=model.source_id,
            speaker_label=model.speaker_label,
            start_time=(
                float(model.start_time) if model.start_time is not None else None
            ),
            end_time=float(model.end_time) if model.end_time is not None else None,
            duration_seconds=(
                float(model.duration_seconds)
                if model.duration_seconds is not None
                else None
            ),
            metadata=dict(model.metadata_ or {}),
            embedding=embedding_list,
            created_at=model.created_at,
        )

    @staticmethod
    def sample_to_model(entity: VoiceSampleEntity) -> VoiceSampleModel:
        source_val = (
            entity.source_type.value
            if isinstance(entity.source_type, VoiceSourceType)
            else str(entity.source_type)
        )
        return VoiceSampleModel(
            id=entity.id or str(uuid.uuid4()),
            speaker_id=entity.speaker_id,
            source_type=source_val,
            source_id=entity.source_id,
            speaker_label=entity.speaker_label,
            start_time=entity.start_time,
            end_time=entity.end_time,
            duration_seconds=entity.duration_seconds,
            metadata_=entity.metadata or {},
            embedding=entity.embedding,
        )
