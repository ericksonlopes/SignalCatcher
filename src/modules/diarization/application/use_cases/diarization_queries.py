from typing import Optional

from src.modules.diarization.application.dtos.diarization_card_dto import (
    DiarizationCardDTO,
)
from src.modules.diarization.application.mappers.diarization_card_mapper import (
    DiarizationCardMapper,
)
from src.modules.diarization.domain.interfaces.repositories.diarization_repository import (
    IDiarizationRepository,
)
from src.modules.youtube.domain.interfaces.services.youtube_content_service import (
    IYoutubeContentService,
)


class DiarizationQueries:
    """Read side of the diarization module.

    This is where the two modules are composed: the repository no longer joins against
    youtube_contents, so the YouTube details are fetched through that module's own
    interface and merged here.
    """

    def __init__(
        self,
        repository: IDiarizationRepository,
        youtube_contents: IYoutubeContentService,
    ):
        self.repository = repository
        self.youtube_contents = youtube_contents

    def get_cards(
        self,
        page: int,
        limit: int,
        step: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple[list[DiarizationCardDTO], int]:
        entity_ids: Optional[list[str]] = None
        if search:
            # Only the youtube module can match a term against video titles and channel
            # names, so it resolves the term into ids first.
            entity_ids = self.youtube_contents.find_external_ids_by_search(search)

        tasks, total = self.repository.get_paginated(
            page=page,
            limit=limit,
            step=step,
            entity_ids=entity_ids,
            entity_id_search=search,
        )

        linked_ids = [task.entity_id for task in tasks if task.entity_id]
        contents = self.youtube_contents.get_many_by_external_ids(linked_ids)

        cards = [
            DiarizationCardMapper.to_card(
                task, contents.get(task.entity_id) if task.entity_id else None
            )
            for task in tasks
        ]
        return cards, total

    def count_by_step(self) -> dict[str, int]:
        return self.repository.count_by_step()

    def get_steps_by_entity_ids(self, entity_ids: list[str]) -> dict[str, str]:
        return self.repository.get_steps_by_entity_ids(entity_ids)
