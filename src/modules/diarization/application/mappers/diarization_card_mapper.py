from src.modules.diarization.application.dtos.diarization_card_dto import (
    PLACEHOLDER_THUMBNAIL,
    UNKNOWN_DURATION,
    UNKNOWN_LABEL,
    DiarizationCardDTO,
)
from src.modules.diarization.domain.entities.diarization_entity import DiarizationEntity
from src.modules.youtube.domain.entities.youtube_content_entity import (
    YoutubeContentEntity,
)


class DiarizationCardMapper:
    @staticmethod
    def to_card(
        task: DiarizationEntity, content: YoutubeContentEntity | None
    ) -> DiarizationCardDTO:
        return DiarizationCardDTO(
            id=task.id or "",
            step=task.step.value,
            created_at=task.created_at.isoformat() if task.created_at else None,
            entity_id=task.entity_id,
            entity_type=task.entity_type,
            title=content.title if content else UNKNOWN_LABEL,
            channelName=content.origin if content else UNKNOWN_LABEL,
            thumbnail=(
                content.thumbnail
                if content and content.thumbnail
                else PLACEHOLDER_THUMBNAIL
            ),
            # Kept as the raw seconds cast to a string, which is what the endpoint has
            # always returned, even though the fallback below is a clock-formatted value.
            duration=(
                str(content.duration)
                if content and content.duration is not None
                else UNKNOWN_DURATION
            ),
            result_json=task.result_json,
        )
