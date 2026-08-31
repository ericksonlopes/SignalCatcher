from typing import Optional, Protocol

from src.modules.diarization.domain.entities.diarization_entity import DiarizationEntity


class IDiarizationRepository(Protocol):
    def create_task(self, task: DiarizationEntity) -> DiarizationEntity:
        """Persists a new diarization task."""
        ...

    def get_task(self, task_id: str) -> Optional[DiarizationEntity]:
        """Returns a task by its own id."""
        ...

    def get_paginated(
        self,
        page: int,
        limit: int,
        step: Optional[str] = None,
        entity_ids: Optional[list[str]] = None,
        entity_id_search: Optional[str] = None,
    ) -> tuple[list[DiarizationEntity], int]:
        """Returns a page of tasks and the total number of matches.

        `entity_ids` restricts the result to those linked entities, and is how a caller
        applies a filter that only the other module can evaluate (a search by video
        title, for example). `entity_id_search` matches the entity id itself.
        """
        ...

    def count_by_step(self) -> dict[str, int]:
        """Returns how many tasks sit in each step."""
        ...

    def get_steps_by_entity_ids(self, entity_ids: list[str]) -> dict[str, str]:
        """Returns the most recent step per linked entity id."""
        ...

    def reprocess_task(self, task_id: str) -> Optional[DiarizationEntity]:
        """Resets a task back to PENDING, clearing its previous result and error."""
        ...

    def cancel_task(self, task_id: str) -> Optional[DiarizationEntity]:
        """Cancels a task that is still in progress.

        Returns None when no task matches. Returns the task untouched when it already
        reached a terminal step, so the caller can tell the two cases apart.
        """
        ...
