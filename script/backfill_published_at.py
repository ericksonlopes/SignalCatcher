import logging
import os
import sys
import datetime

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Add the root directory of the project to PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.repositories.connector import ConnectorPostgres
from src.infrastructure.repositories.models.youtube_content_model import YoutubeContentModel

def main():
    logging.info("Starting backfill for published_at...")

    with ConnectorPostgres() as session:
        # Pega todos os registros que já possuem raw_metadata mas estão sem published_at
        items = session.query(YoutubeContentModel).filter(
            YoutubeContentModel.raw_metadata.isnot(None),
            YoutubeContentModel.published_at.is_(None)
        ).all()

        if not items:
            logging.info("No items found to backfill. Everything is up to date!")
            return

        logging.info(f"Found {len(items)} items to process. Parsing timestamps...")
        
        updated_count = 0
        for item in items:
            raw_meta = item.raw_metadata
            if isinstance(raw_meta, dict):
                timestamp = raw_meta.get('timestamp')
                if timestamp:
                    try:
                        item.published_at = datetime.datetime.fromtimestamp(int(timestamp), tz=datetime.timezone.utc)
                        updated_count += 1
                    except Exception as e:
                        logging.error(f"Error parsing timestamp for item {item.id}: {e}")

        session.commit()
        logging.info(f"Successfully backfilled published_at for {updated_count} items!")

if __name__ == "__main__":
    main()
