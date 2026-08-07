import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Add the root directory of the project to PYTHONPATH so that we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.repositories.connector import ConnectorPostgres
from src.infrastructure.repositories.models.youtube_content_model import (
    YoutubeContentModel,
)
from src.domain.models.enums.content_step import ContentStep
from src.infrastructure.services.youtube_scraper import YouTubeScraperService


class DummyLogger:
    def debug(self, msg, *args, **kwargs):
        logging.debug(msg)

    def info(self, msg, *args, **kwargs):
        logging.info(msg)

    def warning(self, msg, *args, **kwargs):
        logging.warning(msg)

    def error(self, msg, *args, **kwargs):
        logging.error(msg)

    def critical(self, msg, *args, **kwargs):
        logging.critical(msg)


def main():
    logging.info("Starting metadata extraction process...")

    scraper = YouTubeScraperService(logger=DummyLogger())

    while True:
        with ConnectorPostgres() as session:
            # Find one pending metadata extraction
            content = (
                session.query(YoutubeContentModel)
                .filter(
                    YoutubeContentModel.step == ContentStep.PENDING_METADATA_EXTRACTION
                )
                .first()
            )

            if not content:
                logging.info("No more videos pending metadata extraction. Finishing.")
                break

            logging.info(
                f"Extracting metadata for content: {content.title} ({content.url})"
            )

            # Update step to EXTRACTING_METADATA
            content.step = ContentStep.EXTRACTING_METADATA
            session.commit()

            try:
                # Extract metadata using the scraper
                metadata_dict = scraper.extract_metadata(content.url)

                content.raw_metadata = metadata_dict
                content.step = ContentStep.COMPLETED
                session.commit()
                logging.info(f"Successfully extracted metadata for: {content.title}")

            except Exception as e:
                logging.error(f"Error extracting metadata for {content.title}: {e}")
                content.error_info = str(e)
                content.step = ContentStep.ERROR
                session.commit()


if __name__ == "__main__":
    main()
