from src.domain.models.channel_entity import ChannelEntity
from src.infrastructure.repositories.models.youtube_monitored_channel_model import YouTubeMonitoredChannelModel


class ChannelMapper:
    @staticmethod
    def to_domain(model: YouTubeMonitoredChannelModel) -> ChannelEntity:
        return ChannelEntity(
            id=model.id,
            name=model.name,
            url=model.url,
            active=model.active,
            created_at=model.created_at,
            last_checked_at=model.last_checked_at,
        )

    @staticmethod
    def to_model(entity: ChannelEntity) -> YouTubeMonitoredChannelModel:
        return YouTubeMonitoredChannelModel(
            id=entity.id,
            name=entity.name,
            url=entity.url,
            active=entity.active,
            created_at=entity.created_at,
            last_checked_at=entity.last_checked_at,
        )
