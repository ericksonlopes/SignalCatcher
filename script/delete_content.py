import glob
import logging
import os
import re
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Add the root directory of the project to PYTHONPATH so that we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.database.connector import ConnectorPostgres
from src.modules.youtube.infrastructure.repositories.models.youtube_content_model import (
    YoutubeContentModel,
)


def delete_content(external_id: str):
    output_path = r"D:\Youtube"

    with ConnectorPostgres() as session:
        content = session.query(YoutubeContentModel).filter(YoutubeContentModel.external_id == external_id).first()

        if not content:
            logging.error(f"Content with external_id '{external_id}' not found in database.")
            return

        logging.info(f"Found content: {content.title} (Origin: {content.origin})")

        # Determine file path and delete file
        if content.origin:
            safe_origin = re.sub(r'[\\/*?:"<>|]', "_", content.origin)
            final_output_path = os.path.join(output_path, safe_origin)

            # Since the filename is {external_id}_%(title)s.%(ext)s, we can use glob to find it
            search_pattern = os.path.join(final_output_path, f"{external_id}_*")
            matching_files = glob.glob(search_pattern)

            if matching_files:
                for file_path in matching_files:
                    try:
                        os.remove(file_path)
                        logging.info(f"Deleted file: {file_path}")
                    except Exception:
                        logging.exception(f"Failed to delete file {file_path}")
            else:
                logging.warning(f"No file found matching pattern {search_pattern}")
        else:
            logging.warning("Content origin is empty, skipping file deletion.")

        # Delete from DB
        try:
            session.delete(content)
            session.commit()
            logging.info(f"Deleted record for external_id '{external_id}' from database.")
        except Exception:
            session.rollback()
            logging.exception("Failed to delete record from database.")


if __name__ == "__main__":

    target_id = [
        "sUBMwfgTAt0"

    ]

    for external_id in target_id:
        delete_content(external_id)
