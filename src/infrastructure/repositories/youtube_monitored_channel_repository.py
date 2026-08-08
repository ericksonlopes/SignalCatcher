from typing import Optional

from src.domain.interfaces.logger import ILogger
from src.domain.interfaces.youtube_monitored_channel_repository import IYouTubeMonitoredChannelRepository
from src.domain.models.channel_entity import ChannelEntity
from src.infrastructure.repositories.connector import ConnectorPostgres
from src.infrastructure.repositories.mappers.channel_mapper import ChannelMapper
from src.infrastructure.repositories.models.youtube_monitored_channel_model import YouTubeMonitoredChannelModel


class YouTubeMonitoredChannelRepository(IYouTubeMonitoredChannelRepository):
    def __init__(self, logger: ILogger):
        self.logger = logger

    def get_by_url(self, url: str) -> Optional[ChannelEntity]:
        try:
            with ConnectorPostgres() as session:
                channel = session.query(YouTubeMonitoredChannelModel).filter_by(url=url).first()
                if channel:
                    return ChannelMapper.to_domain(channel)
                return None
        except Exception as e:
            self.logger.error(f"Error getting channel by url '{url}': {e}", context={"url": url, "error": str(e)})
            raise

    def create(self, channel_data: ChannelEntity) -> ChannelEntity:
        try:
            with ConnectorPostgres() as session:
                new_channel = ChannelMapper.to_model(channel_data)
                session.add(new_channel)
                session.commit()
                session.refresh(new_channel)
                return ChannelMapper.to_domain(new_channel)
        except Exception as e:
            self.logger.error(f"Error creating channel '{channel_data.url}': {e}",
                              context={"url": channel_data.url, "error": str(e)})
            raise

    def get_all_active(self) -> list[ChannelEntity]:
        try:
            with ConnectorPostgres() as session:
                channels = session.query(YouTubeMonitoredChannelModel).filter_by(active=True).all()
                return [ChannelMapper.to_domain(c) for c in channels]
        except Exception as e:
            self.logger.error(f"Error getting all active channels: {e}", context={"error": str(e)})
            raise

    def get_all(self) -> list[ChannelEntity]:
        try:
            with ConnectorPostgres() as session:
                channels = session.query(YouTubeMonitoredChannelModel).all()
                return [ChannelMapper.to_domain(c) for c in channels]
        except Exception as e:
            self.logger.error(f"Error getting all channels: {e}", context={"error": str(e)})
            raise

    def update(self, channel_entity: ChannelEntity) -> ChannelEntity:
        try:
            with ConnectorPostgres() as session:
                model = session.query(YouTubeMonitoredChannelModel).filter_by(id=channel_entity.id).first()
                if model:
                    model.last_checked_at = channel_entity.last_checked_at
                    model.active = channel_entity.active
                    # Update other fields if necessary
                    session.commit()
                    session.refresh(model)
                    return ChannelMapper.to_domain(model)
                return channel_entity  # Or raise an exception
        except Exception as e:
            self.logger.error(f"Error updating channel '{channel_entity.id}': {e}",
                              context={"channel_id": channel_entity.id, "error": str(e)})
            raise
