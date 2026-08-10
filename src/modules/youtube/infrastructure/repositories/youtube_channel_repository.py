from src.core.database.connector import ConnectorPostgres
from src.core.logger.interfaces import ILogger
from src.modules.youtube.domain.interfaces.repositories.youtube_channel_repository import (
    IYouTubeChannelRepository,
)
from src.modules.youtube.infrastructure.repositories.models.youtube_channel_model import (
    YouTubeChannelModel,
)


class YouTubeChannelRepository(IYouTubeChannelRepository):
    def __init__(self, logger: ILogger):
        self.logger = logger

    def upsert_channel(self, channel_info: dict) -> None:
        """
        Inserts or updates a YouTube channel metadata record.
        """
        try:
            with ConnectorPostgres() as session:
                external_id = channel_info.get("id")

                # Check if it exists
                existing_channel = (
                    session.query(YouTubeChannelModel)
                    .filter_by(external_id=external_id)
                    .first()
                )

                if existing_channel:
                    # Update
                    existing_channel.title = channel_info.get("title")
                    existing_channel.description = channel_info.get("description")
                    existing_channel.url = channel_info.get("url")
                    existing_channel.channel_url = channel_info.get("channel_url")
                    existing_channel.thumbnails = channel_info.get("thumbnails")
                    self.logger.debug(
                        f"YouTubeChannel '{external_id}' updated in database."
                    )
                else:
                    # Insert
                    new_channel = YouTubeChannelModel(
                        external_id=external_id,
                        title=channel_info.get("title"),
                        description=channel_info.get("description"),
                        url=channel_info.get("url"),
                        channel_url=channel_info.get("channel_url"),
                        thumbnails=channel_info.get("thumbnails"),
                    )
                    session.add(new_channel)
                    self.logger.debug(
                        f"YouTubeChannel '{external_id}' added to database."
                    )

                session.commit()
        except Exception as e:
            self.logger.error(
                f"Error upserting youtube channel '{channel_info.get('url')}': {e}",
                context={"error": str(e)},
            )
            raise

    def get_all(self) -> list[YouTubeChannelModel]:
        """
        Retrieves all saved YouTube channels.
        """
        try:
            with ConnectorPostgres() as session:
                from sqlalchemy import func
                from src.modules.youtube.infrastructure.repositories.models.youtube_content_model import (
                    YoutubeContentModel,
                )

                results = (
                    session.query(
                        YouTubeChannelModel,
                        func.count(YoutubeContentModel.id).label("video_count"),
                    )
                    .outerjoin(
                        YoutubeContentModel,
                        YoutubeContentModel.origin == YouTubeChannelModel.external_id,
                    )
                    .group_by(YouTubeChannelModel.id)
                    .order_by(func.count(YoutubeContentModel.id).desc())
                    .all()
                )

                # Add video_count dynamically to the object so the DTO mapper can pick it up
                channels = []
                for channel, count in results:
                    channel.video_count = count
                    channels.append(channel)
                return channels
        except Exception as e:
            self.logger.error(
                "Error retrieving saved youtube channels", context={"error": str(e)}
            )
            raise
