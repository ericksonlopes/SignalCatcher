from src.domain.interfaces.logger import ILogger
from src.infrastructure.repositories.connector import ConnectorPostgres
from src.infrastructure.repositories.models.youtube_channel_model import (
    YouTubeChannelModel,
)


class YouTubeChannelRepository:
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
