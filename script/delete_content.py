import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse

from src.core.database.job_control import JobControlRepository
from src.core.logger.logger import logger
from src.modules.youtube.infrastructure.unit_of_work import YoutubeUnitOfWork


def delete_content(external_id: str) -> None:
    with YoutubeUnitOfWork(logger=logger) as uow:
        if not uow.contents.request_deletion(external_id):
            raise ValueError("Content not found.")
        JobControlRepository(uow.session).request("youtube_delete_contents")
        uow.commit()
    logger.info(f"Deletion queued for {external_id}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Queue a safe, recoverable content deletion.")
    parser.add_argument("external_id")
    delete_content(parser.parse_args().external_id)
