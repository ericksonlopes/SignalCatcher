import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Add the root directory of the project to PYTHONPATH so that we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.infrastructure.repositories.connector import ConnectorPostgres

def migrate_downloaded_to_metadata():
    logging.info("Starting migration of DOWNLOADED to PENDING_METADATA_EXTRACTION...")
    
    with ConnectorPostgres() as session:
        try:
            # Using raw SQL to avoid Enum validation errors since 'DOWNLOADED' was removed from ContentStep
            # If the column is still named 'status' in DB (before alembic upgrade), we should update 'status'
            # But the script assumes you will run this AFTER alembic upgrade head (when it's named 'step').
            # To be safe and support both, let's try updating 'step', and if it fails, try 'status'.
            
            try:
                result = session.execute(
                    text("UPDATE youtube_contents SET step = 'PENDING_METADATA_EXTRACTION' WHERE step = 'DOWNLOADED'")
                )
            except Exception as e:
                logging.warning("Failed to update 'step' column. Attempting 'status' column if migration was not run yet.")
                session.rollback()
                result = session.execute(
                    text("UPDATE youtube_contents SET status = 'PENDING_METADATA_EXTRACTION' WHERE status = 'DOWNLOADED'")
                )
            
            session.commit()
            logging.info(f"Migration completed successfully! {result.rowcount} records were updated.")
            
        except Exception as e:
            logging.error(f"Error during migration: {e}")
            session.rollback()


if __name__ == "__main__":
    migrate_downloaded_to_metadata()
