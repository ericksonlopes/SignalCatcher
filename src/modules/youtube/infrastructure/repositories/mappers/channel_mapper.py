from src.modules.youtube.domain.entities.channel_entity import ChannelEntity
from src.modules.youtube.infrastructure.repositories.models.youtube_monitored_channel_model import (
    YouTubeMonitoredChannelModel,
)


class ChannelMapper:
    @staticmethod
    def to_domain(model: YouTubeMonitoredChannelModel) -> ChannelEntity:
        return ChannelEntity(
            id=model.id,
            external_id=model.external_id,
            name=model.channel_info.title if model.channel_info else model.external_id,
            url=model.url,
            active=model.active,
            created_at=model.created_at,
            last_checked_at=model.last_checked_at,
        )

    @staticmethod
    def to_model(entity: ChannelEntity) -> YouTubeMonitoredChannelModel:
        return YouTubeMonitoredChannelModel(
            id=entity.id,
            external_id=entity.external_id,
            url=entity.url,
            active=entity.active,
            created_at=entity.created_at,
            last_checked_at=entity.last_checked_at,
        )
