import argparse
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Add the root directory of the project to PYTHONPATH so that we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.repositories.connector import ConnectorPostgres
from src.infrastructure.repositories.models.content_model import ContentModel
from src.domain.models.enums.content_status import ContentStatus


def process_non_mp4_files(directory):
    if not os.path.exists(directory):
        logging.error(f"Directory does not exist: {directory}")
        return

    non_mp4_files = []

    # Iterate through all files and subdirectories
    for root, dirs, files in os.walk(directory):
        for file in files:
            # Check if file does not end with .mp4 (case insensitive)
            if not file.lower().endswith('.mp4'):
                full_path = os.path.join(root, file)
                non_mp4_files.append((file, full_path))

    if not non_mp4_files:
        logging.info("All files in the directory are MP4s! No errors found.")
        return

    logging.info(f"Found {len(non_mp4_files)} files that are not MP4. Checking database...")

    with ConnectorPostgres() as session:
        for file_name, file_path in non_mp4_files:
            # Extacting the ID (Since filename format is ID_Title.ext, ID is before the first underscore)
            external_id = file_name.split('_')[0]

            # Search the database using the extracted ID
            content = session.query(ContentModel).filter(
                ContentModel.external_id == external_id
            ).first()

            if content:
                logging.info(f"ID {external_id} found in DB! (File: {file_name})")

                # Reset status to PENDING_DOWNLOAD to restart download later
                if content.status != ContentStatus.PENDING_DOWNLOAD:
                    content.status = ContentStatus.PENDING_DOWNLOAD
                    content.error_info = f"Found incomplete/wrong format file: {file_name}"
                    session.commit()
                    logging.info(f" {content.title} -> Status alterado para PENDING_DOWNLOAD")
                else:
                    logging.info(f" {content.title} -> Status já estava como PENDING_DOWNLOAD")

                # We delete the broken/incomplete file so it downloads completely from scratch next time
                try:
                    os.remove(file_path)
                    logging.info(f" {content.title} -> Arquivo incompleto deletado do disco.")
                except Exception as e:
                    logging.error(f" {content.title} -> Falha ao deletar arquivo: {e}")

            else:
                logging.warning(
                    f"ID {external_id} do arquivo {file_name} não foi encontrado no banco de dados. Ignorando.")

            logging.info("-" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Find files that are not MP4, delete them, and reset their DB status to PENDING_DOWNLOAD.")
    # Set default path to D:\Youtube
    parser.add_argument("--path", type=str, default=r"D:\Youtube", help="Path to the directory to scan")

    args = parser.parse_args()

    logging.info(f"Scanning directory: {args.path}")
    process_non_mp4_files(args.path)
