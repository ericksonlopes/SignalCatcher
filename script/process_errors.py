import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Add the root directory of the project to PYTHONPATH so that we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Add the script directory to PYTHONPATH to import download_video
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.infrastructure.repositories.connector import ConnectorPostgres
from src.infrastructure.repositories.models.youtube_content_model import YoutubeContentModel
from src.domain.models.enums.content_step import ContentStep
from download_videos import download_video


def main():
    logging.info("Starting error retry process...")
    output_path = r"D:\Youtube"

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
                download_video(url=content.url, content_id=content.external_id, origin=content.origin,
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


if __name__ == "__main__":
    main()
