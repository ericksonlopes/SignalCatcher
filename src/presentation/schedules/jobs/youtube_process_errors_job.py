import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


from src.infrastructure.repositories.connector import ConnectorPostgres
from src.infrastructure.repositories.models.youtube_content_model import YoutubeContentModel
from src.domain.models.enums.content_step import ContentStep
from src.infrastructure.services.youtube_scraper import YouTubeScraperService
from src.infrastructure.loggers.logger import logger as global_logger
from src.config.settings import settings


def process_errors_job():
    logging.info("Starting error retry process...")
    output_path = settings.DOWNLOAD_YOUTUBE_PATH
    scraper = YouTubeScraperService(logger=global_logger)

    with ConnectorPostgres() as session:
        # Find all videos that failed previously
        error_contents = session.query(YoutubeContentModel).filter(
            YoutubeContentModel.step == ContentStep.ERROR
        ).all()

        if not error_contents:
            logging.info("No videos with ERROR step found.")
            return

        logging.info(f"Found {len(error_contents)} videos to retry.")

        for content in error_contents:
            logging.info(f"Retrying content: {content.title} ({content.url})")
            logging.warning(f"Previous Error: {content.error_info}")

            # Update step to DOWNLOADING
            content.step = ContentStep.DOWNLOADING
            session.commit()

            try:
                scraper.download_video(url=content.url, content_id=content.external_id, origin=content.origin,
                                       output_path=output_path)

                # Update step to PENDING_METADATA_EXTRACTION and clear error info
                content.step = ContentStep.PENDING_METADATA_EXTRACTION
                content.error_info = None
                session.commit()
                logging.info(f"Successfully downloaded on retry: {content.title}")
            except Exception as e:
                error_msg = str(e).lower()
                logging.error(f"Error downloading again {content.title}: {e}")
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


def reprocess_single_video_job(external_id: str):
    logging.info(f"Starting individual reprocessing for video {external_id}...")
    output_path = settings.DOWNLOAD_YOUTUBE_PATH
    scraper = YouTubeScraperService(logger=global_logger)

    with ConnectorPostgres() as session:
        content = session.query(YoutubeContentModel).filter(
            YoutubeContentModel.external_id == external_id
        ).first()

        if not content:
            logging.error(f"Cannot reprocess: Content {external_id} not found.")
            return

        # Double check it is actually in REPROCESSING
        if content.step != ContentStep.REPROCESSING:
            logging.warning(f"Video {external_id} is not in REPROCESSING state. Aborting.")
            return

        try:
            # We don't know where it failed, but since it's a full reprocess:
            # First extract metadata if missing or as a fresh start
            logging.info(f"Reprocessing {content.title}: Extracting metadata...")
            info_dict = scraper.extract_metadata(video_url=content.url)
            
            content.raw_metadata = info_dict
            if info_dict:
                content.thumbnail = info_dict.get('thumbnail')
                
                # Format duration HH:MM:SS
                duration_sec = info_dict.get('duration')
                if duration_sec:
                    import time
                    content.duration = time.strftime('%H:%M:%S', time.gmtime(duration_sec))
                    
                content.categories = info_dict.get('categories', [])
                content.tags = info_dict.get('tags', [])
                
                pub_date_str = info_dict.get('upload_date')
                if pub_date_str and len(pub_date_str) == 8:
                    from datetime import datetime
                    content.published_at = datetime.strptime(pub_date_str, '%Y%m%d')
            
            session.commit()
            
            # Now download
            logging.info(f"Reprocessing {content.title}: Downloading...")
            scraper.download_video(url=content.url, content_id=content.external_id, origin=content.origin,
                                   output_path=output_path)
            
            # Finished
            content.step = ContentStep.COMPLETED
            content.error_info = None
            session.commit()
            logging.info(f"Successfully reprocessed: {content.title}")
            
        except Exception as e:
            error_msg = str(e).lower()
            logging.error(f"Error reprocessing {content.title}: {e}")
            content.error_info = str(e)
            
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


if __name__ == "__main__":
    process_errors_job()
