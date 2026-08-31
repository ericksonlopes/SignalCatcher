from sqlalchemy import func
from sqlalchemy.orm import Session

from src.core.logger.interfaces import ILogger
from src.modules.youtube.domain.interfaces.repositories.youtube_channel_repository import (
    IYouTubeChannelRepository,
)
from src.modules.youtube.infrastructure.repositories.models.youtube_channel_model import (
    YouTubeChannelModel,
)
from src.modules.youtube.infrastructure.repositories.models.youtube_content_model import (
    YoutubeContentModel,
)


class YouTubeChannelRepository(IYouTubeChannelRepository):
    """Persistence for channel metadata.

    Takes part in the caller's transaction: writes flush but never commit, so the
    unit of work decides when the operation is complete.
    """

    def __init__(self, session: Session, logger: ILogger):
        self.session = session
        self.logger = logger

    def upsert_channel(self, channel_info: dict) -> None:
        """
        Inserts or updates a YouTube channel metadata record.
        """
        try:
            external_id = channel_info.get("id")

            # Check if it exists
            existing_channel = (
                self.session.query(YouTubeChannelModel)
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
                self.session.add(new_channel)
                self.logger.debug(f"YouTubeChannel '{external_id}' added to database.")

            self.session.flush()
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
            results = (
                self.session.query(
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
