from src.modules.diarization.domain.entities.diarization_entity import DiarizationEntity
from src.modules.diarization.domain.enums.diarization_step import DiarizationStep
from src.modules.diarization.infrastructure.repositories.models.diarization_model import (
    DiarizationModel,
)


class DiarizationMapper:
    @staticmethod
    def to_domain(model: DiarizationModel) -> DiarizationEntity:
        return DiarizationEntity(
            id=model.id,
            file_path=model.file_path,
            # Stored as free text, so an unrecognised value falls back to ERROR rather
            # than blowing up the whole listing.
            step=DiarizationMapper._to_step(model.step),
            entity_id=model.entity_id,
            entity_type=model.entity_type,
            language=model.language,
            num_speakers=model.num_speakers,
            min_speakers=model.min_speakers,
            max_speakers=model.max_speakers,
            model_size=model.model_size,
            result_json=model.result_json,
            error_message=model.error_message,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def to_model(entity: DiarizationEntity) -> DiarizationModel:
        return DiarizationModel(
            file_path=entity.file_path,
            step=entity.step.value,
            entity_id=entity.entity_id,
            entity_type=entity.entity_type,
            language=entity.language,
            num_speakers=entity.num_speakers,
            min_speakers=entity.min_speakers,
            max_speakers=entity.max_speakers,
            model_size=entity.model_size,
            result_json=entity.result_json,
            error_message=entity.error_message,
        )

    @staticmethod
    def _to_step(raw: str | None) -> DiarizationStep:
        try:
            return DiarizationStep(raw)
        except ValueError:
            return DiarizationStep.ERROR
