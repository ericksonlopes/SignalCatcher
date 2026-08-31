from typing import Optional

from sqlalchemy.orm import Session, joinedload

from src.core.logger.interfaces import ILogger
from src.modules.youtube.domain.entities.channel_entity import ChannelEntity
from src.modules.youtube.domain.interfaces.repositories.youtube_monitored_channel_repository import (
    IYouTubeMonitoredChannelRepository,
)
from src.modules.youtube.infrastructure.repositories.mappers.channel_mapper import (
    ChannelMapper,
)
from src.modules.youtube.infrastructure.repositories.models.youtube_monitored_channel_model import (
    YouTubeMonitoredChannelModel,
)


class YouTubeMonitoredChannelRepository(IYouTubeMonitoredChannelRepository):
    """Persistence for monitored channels.

    Takes part in the caller's transaction: writes flush but never commit, so the
    unit of work decides when the operation is complete.
    """

    def __init__(self, session: Session, logger: ILogger):
        self.session = session
        self.logger = logger

    def get_by_url(self, url: str) -> Optional[ChannelEntity]:
        try:
            channel = (
                self.session.query(YouTubeMonitoredChannelModel)
                .options(joinedload(YouTubeMonitoredChannelModel.channel_info))
                .filter_by(url=url)
                .first()
            )
            if channel:
                return ChannelMapper.to_domain(channel)
            return None
        except Exception as e:
            self.logger.error(
                f"Error getting channel by url '{url}': {e}",
                context={"url": url, "error": str(e)},
            )
            raise

    def get_by_id(self, channel_id: int) -> Optional[ChannelEntity]:
        try:
            channel = (
                self.session.query(YouTubeMonitoredChannelModel)
                .options(joinedload(YouTubeMonitoredChannelModel.channel_info))
                .filter_by(id=channel_id)
                .first()
            )
            if channel:
                return ChannelMapper.to_domain(channel)
            return None
        except Exception as e:
            self.logger.error(
                f"Error getting channel by id '{channel_id}': {e}",
                context={"channel_id": channel_id, "error": str(e)},
            )
            raise

    def create(self, channel_data: ChannelEntity) -> ChannelEntity:
        try:
            new_channel = ChannelMapper.to_model(channel_data)
            self.session.add(new_channel)
            self.session.flush()
            self.session.refresh(new_channel)
            return ChannelMapper.to_domain(new_channel)
        except Exception as e:
            self.logger.error(
                f"Error creating channel '{channel_data.url}': {e}",
                context={"url": channel_data.url, "error": str(e)},
            )
            raise

    def get_all_active(self) -> list[ChannelEntity]:
        try:
            channels = (
                self.session.query(YouTubeMonitoredChannelModel)
                .options(joinedload(YouTubeMonitoredChannelModel.channel_info))
                .filter_by(active=True)
                .all()
            )
            return [ChannelMapper.to_domain(c) for c in channels]
        except Exception as e:
            self.logger.error(
                f"Error getting all active channels: {e}", context={"error": str(e)}
            )
            raise

    def get_all(self) -> list[ChannelEntity]:
        try:
            channels = (
                self.session.query(YouTubeMonitoredChannelModel)
                .options(joinedload(YouTubeMonitoredChannelModel.channel_info))
                .all()
            )
            return [ChannelMapper.to_domain(c) for c in channels]
        except Exception as e:
            self.logger.error(
                f"Error getting all channels: {e}", context={"error": str(e)}
            )
            raise

    def update(self, channel_entity: ChannelEntity) -> ChannelEntity:
        try:
            model = (
                self.session.query(YouTubeMonitoredChannelModel)
                .filter_by(id=channel_entity.id)
                .first()
            )
            if model:
                model.last_checked_at = channel_entity.last_checked_at
                model.active = channel_entity.active
                # Update other fields if necessary
                self.session.flush()
                self.session.refresh(model)
                return ChannelMapper.to_domain(model)
            return channel_entity  # Or raise an exception
        except Exception as e:
            self.logger.error(
                f"Error updating channel '{channel_entity.id}': {e}",
                context={"channel_id": channel_entity.id, "error": str(e)},
            )
            raise
