import argparse
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Add the root directory of the project to PYTHONPATH so that we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.core.database.connector import ConnectorPostgres
from src.modules.youtube.domain.enums.content_step import ContentStep
from src.modules.youtube.infrastructure.repositories.models.youtube_content_model import (
    YoutubeContentModel,
)


def _collect_non_mp4_files(directory):
    """Returns (file_name, full_path) for every non-mp4 file under the directory."""
    non_mp4_files = []
    for root, _dirs, files in os.walk(directory):
        for file in files:
            if not file.lower().endswith('.mp4'):
                non_mp4_files.append((file, os.path.join(root, file)))
    return non_mp4_files


def _reset_content_step(session, content, file_name):
    """Moves a content back to PENDING_DOWNLOAD so it is re-downloaded from scratch."""
    if content.step != ContentStep.PENDING_DOWNLOAD:
        content.step = ContentStep.PENDING_DOWNLOAD
        content.error_info = f"Found incomplete/wrong format file: {file_name}"
        session.commit()
        logging.info(f" {content.title} -> Step alterado para PENDING_DOWNLOAD")
    else:
        logging.info(f" {content.title} -> Step já estava como PENDING_DOWNLOAD")


def _delete_broken_file(file_path, title):
    try:
        os.remove(file_path)
        logging.info(f" {title} -> Arquivo incompleto deletado do disco.")
    except Exception:
        logging.exception(f" {title} -> Falha ao deletar arquivo.")


def _handle_non_mp4_file(session, file_name, file_path):
    # Filename format is ID_Title.ext, so the external id is before the first underscore.
    external_id = file_name.split('_')[0]
    content = session.query(YoutubeContentModel).filter(
        YoutubeContentModel.external_id == external_id
    ).first()

    if not content:
        logging.warning(
            f"ID {external_id} do arquivo {file_name} não foi encontrado no banco de dados. Ignorando."
        )
        return

    logging.info(f"ID {external_id} found in DB! (File: {file_name})")
    _reset_content_step(session, content, file_name)
    _delete_broken_file(file_path, content.title)


def process_non_mp4_files(directory):
    if not os.path.exists(directory):
        logging.error(f"Directory does not exist: {directory}")
        return

    non_mp4_files = _collect_non_mp4_files(directory)
    if not non_mp4_files:
        logging.info("All files in the directory are MP4s! No errors found.")
        return

    logging.info(f"Found {len(non_mp4_files)} files that are not MP4. Checking database...")

    with ConnectorPostgres() as session:
        for file_name, file_path in non_mp4_files:
            _handle_non_mp4_file(session, file_name, file_path)
            logging.info("-" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Find files that are not MP4, delete them, and reset their DB status to PENDING_DOWNLOAD.")
    # Set default path to D:\Youtube
    parser.add_argument("--path", type=str, default=r"D:\Youtube", help="Path to the directory to scan")

    args = parser.parse_args()

    logging.info(f"Scanning directory: {args.path}")
    process_non_mp4_files(args.path)
