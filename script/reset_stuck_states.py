import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.repositories.connector import ConnectorPostgres
from src.infrastructure.repositories.models.youtube_content_model import YoutubeContentModel
from src.domain.models.enums.content_step import ContentStep

def main():
    logging.info("Searching for zombie items stuck in processing states...")

    stuck_mapping = {
        ContentStep.ERROR: ContentStep.VIDEO_REMOVED,
    }

    with ConnectorPostgres() as session:
        for stuck_step, pending_step in stuck_mapping.items():
            stuck_items = session.query(YoutubeContentModel).filter(
                YoutubeContentModel.step == stuck_step
            ).all()

            if stuck_items:
                logging.info(f"Found {len(stuck_items)} items stuck in {stuck_step.name}. Resetting to {pending_step.name}...")
                for item in stuck_items:
                    item.step = pending_step
            else:
                logging.info(f"No items stuck in {stuck_step.name}.")

        session.commit()
        logging.info("Successfully cleaned up stuck items!")

if __name__ == "__main__":
    main()
