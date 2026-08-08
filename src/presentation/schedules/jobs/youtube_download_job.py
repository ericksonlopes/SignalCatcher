import logging
import os
import re
import sys

import yt_dlp

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from src.domain.models.enums.content_step import ContentStep
from src.infrastructure.repositories.connector import ConnectorPostgres
from src.infrastructure.repositories.models.youtube_content_model import YoutubeContentModel
import src.infrastructure.repositories.models.step_tracking_model  # Register SQLAlchemy events
from src.config.settings import settings

from src.infrastructure.services.youtube_scraper import YouTubeScraperService
from src.infrastructure.loggers.logger import logger as global_logger


def download_videos_job():
    logging.info("Starting video download process...")
    output_path = settings.DOWNLOAD_YOUTUBE_PATH
    scraper = YouTubeScraperService(logger=global_logger)
    while True:
        with ConnectorPostgres() as session:
            # Find one pending download
            content = session.query(YoutubeContentModel).filter(
                YoutubeContentModel.step == ContentStep.PENDING_DOWNLOAD
            ).first()

            if not content:
                logging.info("No more videos pending download. Finishing.")
                break

            logging.info(f"Processing content: {content.title} ({content.url})")

            # Update step to DOWNLOADING
            content.step = ContentStep.DOWNLOADING
            session.commit()

            try:
                scraper.download_video(url=content.url, content_id=content.external_id, origin=content.origin,
                                       output_path=output_path)

                # Update step to DOWNLOADED
                content.step = ContentStep.DOWNLOADED
                session.commit()

                # Update step to COMPLETED
                content.step = ContentStep.COMPLETED
                session.commit()
                logging.info(f"Successfully downloaded: {content.title}")
            except Exception as e:
                error_msg = str(e).lower()
                logging.error(f"Error downloading {content.title}: {e}")
                # Save error info
                content.error_info = str(e)
                # Check if it's a members-only error
                if "members-only content like this video" in error_msg or "members on level" in error_msg:
                    content.step = ContentStep.MEMBERS_ONLY
                elif "sign in to confirm your age" in error_msg:
                    content.step = ContentStep.AGE_RESTRICTED
                elif "private video" in error_msg and "sign in if you've been granted access" in error_msg:
                    content.step = ContentStep.PRIVATE_VIDEO
                elif "removed following a copyright" in error_msg:
                    content.step = ContentStep.COPYRIGHT_REMOVED
                elif "account associated with this video has been terminated" in error_msg:
                    content.step = ContentStep.ACCOUNT_TERMINATED
                else:
                    content.step = ContentStep.ERROR
                session.commit()

                # Check for YouTube bot detection
                if "sign in to confirm you’re not a bot" in error_msg or "sign in to confirm you're not a bot" in error_msg:
                    logging.critical("YouTube bot detection triggered! Stopping the system to prevent IP ban.")
                    sys.exit(1)


if __name__ == "__main__":
    download_videos_job()
