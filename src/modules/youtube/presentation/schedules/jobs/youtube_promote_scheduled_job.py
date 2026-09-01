from src.core.logger.logger import logger as global_logger
from src.modules.youtube.application.use_cases.jobs.promote_scheduled_use_case import (
    PromoteScheduledUseCase,
)
from src.modules.youtube.infrastructure.unit_of_work import YoutubeUnitOfWork


def promote_scheduled_job():
    global_logger.info("Starting scheduled-premiere promotion process...")

    use_case = PromoteScheduledUseCase(
        uow_factory=lambda: YoutubeUnitOfWork(logger=global_logger),
        logger=global_logger,
    )

    try:
        promoted = use_case.execute()
        global_logger.info(
            f"Scheduled-premiere promotion finished. {promoted} videos re-queued."
        )
    except Exception as e:
        global_logger.error(f"Scheduled-premiere promotion job aborted: {e}")


if __name__ == "__main__":
    promote_scheduled_job()
