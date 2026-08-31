from typing import Optional
from src.modules.diarization.infrastructure.repositories.diarization_repository import DiarizationRepository
from src.modules.diarization.infrastructure.repositories.models.diarization_model import DiarizationModel

class DiarizationService:
    def __init__(self):
        self.repository = DiarizationRepository()

    def create_task(
        self,
        file_path: str,
        entity_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        language: Optional[str] = None,
        num_speakers: Optional[int] = None,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None,
        model_size: str = "large-v2"
    ) -> DiarizationModel:
        if not file_path:
            raise ValueError("O file_path é obrigatório para a diarização.")
            
        return self.repository.create_task(
            file_path=file_path,
            entity_id=entity_id,
            entity_type=entity_type,
            language=language,
            num_speakers=num_speakers,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
            model_size=model_size
        )

    def get_all_diarizations(self) -> list[DiarizationModel]:
        return self.repository.get_all_diarizations()

    def get_diarizations_with_details(
        self,
        page: int = 1,
        limit: int = 20,
        step: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple[list[dict], int]:
        return self.repository.get_diarizations_with_details(
            page=page, limit=limit, step=step, search=search
        )

    def count_by_step(self) -> dict[str, int]:
        return self.repository.count_by_step()

    def get_diarization_statuses_by_entity_ids(self, entity_ids: list[str]) -> dict[str, str]:
        return self.repository.get_diarization_statuses_by_entity_ids(entity_ids)

    def reprocess_task(self, task_id: str) -> Optional[DiarizationModel]:
        return self.repository.reprocess_task(task_id)

    def cancel_task(self, task_id: str) -> Optional[DiarizationModel]:
        return self.repository.cancel_task(task_id)
