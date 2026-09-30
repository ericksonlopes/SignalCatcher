from src.modules.diarization.domain.entities.diarization_entity import DiarizationEntity
from src.modules.diarization.domain.enums.diarization_step import DiarizationStep
from src.modules.diarization.domain.interfaces.repositories.diarization_repository import (
    IDiarizationRepository,
)


class DiarizationCommands:
    """Write side of the diarization module."""

    def __init__(self, repository: IDiarizationRepository):
        self.repository = repository

    def create_task(
        self,
        file_path: str,
        entity_id: str | None = None,
        entity_type: str | None = None,
        language: str | None = None,
        num_speakers: int | None = None,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
        model_size: str = "large-v2",
    ) -> DiarizationEntity:
        if not file_path:
            raise ValueError("O file_path é obrigatório para a diarização.")

        task = DiarizationEntity(
            file_path=file_path,
            step=DiarizationStep.PENDING,
            entity_id=entity_id,
            entity_type=entity_type,
            language=language,
            num_speakers=num_speakers,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
            model_size=model_size,
        )
        return self.repository.create_task(task)

    def reprocess_task(self, task_id: str) -> DiarizationEntity | None:
        return self.repository.reprocess_task(task_id)

    def cancel_task(self, task_id: str) -> DiarizationEntity | None:
        return self.repository.cancel_task(task_id)

    def prioritize_task(self, task_id: str) -> DiarizationEntity | None:
        return self.repository.prioritize_task(task_id)
