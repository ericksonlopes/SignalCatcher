import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.logger.logger import logger
from src.modules.youtube.infrastructure.unit_of_work import YoutubeUnitOfWork


def main() -> None:
    with YoutubeUnitOfWork(logger=logger) as uow:
        count = uow.contents.recover_expired_leases()
        uow.commit()
    logger.info(f"Recovered {count} expired content reservations.")


if __name__ == "__main__":
    main()
