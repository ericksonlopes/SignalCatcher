from collections.abc import Callable

from src.core.logger.interfaces import ILogger
from src.modules.youtube.domain.enums.content_step import ContentStep
from src.modules.youtube.domain.error_classifier import (
    classify_youtube_error,
    is_bot_block,
)
from src.modules.youtube.domain.interfaces.services.scraper import IYouTubeScraper
from src.modules.youtube.domain.interfaces.unit_of_work import IYoutubeUnitOfWork


class ProcessErrorsUseCase:
    def __init__(
        self,
        uow_factory: Callable[[], IYoutubeUnitOfWork],
        scraper: IYouTubeScraper,
        output_path: str,
        logger: ILogger,
    ):
        self.uow_factory = uow_factory
        self.scraper = scraper
        self.output_path = output_path
        self.logger = logger

    def execute(self) -> int:
        """Retries downloading all videos currently in ERROR step.

        Returns the number of videos attempted.
        Raises Exception if YouTube bot detection is triggered.

        Each attempt uses its own short transactions, so one failing video never
        rolls back the outcome already recorded for the previous ones.
        """
        retried_count = 0
        tried_ids: set[str] = set()

        while True:
            # Claim the next errored video and mark it in progress.
            with self.uow_factory() as uow:
                content = uow.contents.get_first_by_step(ContentStep.ERROR)
                if not content or content.external_id in tried_ids:
                    break

                tried_ids.add(content.external_id)
                self.logger.info(f"Retrying content: {content.title} ({content.url})")
                if content.error_info:
                    self.logger.warning(f"Previous Error: {content.error_info}")

                content.step = ContentStep.DOWNLOADING
                content = uow.contents.update_content(content)
                uow.commit()

            retried_count += 1

            try:
                # The download runs outside any transaction: it can take hours.
                self.scraper.download_video(
                    url=content.url,
                    content_id=content.external_id,
                    origin=content.origin,
                    output_path=self.output_path,
                )

                # On successful retry, reset to PENDING_METADATA_EXTRACTION and clear
                # the stale error in the same transaction.
                with self.uow_factory() as uow:
                    content.step = ContentStep.PENDING_METADATA_EXTRACTION
                    content.error_info = None
                    uow.contents.update_content(content)
                    uow.commit()

                self.logger.info(f"Successfully downloaded on retry: {content.title}")

            except Exception as e:
                error_msg = str(e)
                self.logger.error(
                    f"Error downloading again {content.title}: {error_msg}"
                )

                classified_step = classify_youtube_error(error_msg)

                with self.uow_factory() as uow:
                    content.error_info = error_msg
                    content.step = classified_step
                    uow.contents.update_content(content)
                    uow.commit()

                # See DownloadVideoUseCase: only an unclassified failure can be a
                # bot block, so a recognised per-video restriction keeps the retry
                # loop going instead of aborting it.
                if classified_step is ContentStep.ERROR and is_bot_block(error_msg):
                    self.logger.critical(
                        "YouTube bot block detected! Aborting error retry."
                    )
                    raise

        return retried_count
