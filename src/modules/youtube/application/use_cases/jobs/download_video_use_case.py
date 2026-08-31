import os
from collections.abc import Callable

from src.core.logger.interfaces import ILogger
from src.core.utils.file_utils import format_storage_path
from src.modules.youtube.domain.enums.content_step import ContentStep
from src.modules.youtube.domain.error_classifier import (
    classify_youtube_error,
    is_bot_block,
)
from src.modules.youtube.domain.interfaces.services.scraper import IYouTubeScraper
from src.modules.youtube.domain.interfaces.unit_of_work import IYoutubeUnitOfWork


class DownloadVideoUseCase:
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

    def execute(self) -> bool:
        """Downloads one pending video.

        Returns True if a video was processed, False if no pending videos remain.
        Raises Exception if YouTube bot detection is triggered.

        The work is split into three phases with their own transactions. The download
        sits between them on purpose: it can run for hours, and holding a transaction
        open across it would pin a connection and keep the row locked the whole time.
        """
        # Phase 1: claim one pending video and commit, so the DOWNLOADING step is
        # visible while the download runs.
        with self.uow_factory() as uow:
            content = uow.contents.get_first_by_step(ContentStep.PENDING_DOWNLOAD)

            if not content:
                return False

            self.logger.info(f"Processing download: {content.title} ({content.url})")

            content.step = ContentStep.DOWNLOADING
            content = uow.contents.update_content(content)
            uow.commit()

        # Phase 2: the actual download, outside any transaction.
        try:
            final_file_path = self.scraper.download_video(
                url=content.url,
                content_id=content.external_id,
                origin=content.origin,
                output_path=self.output_path,
            )
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Error downloading {content.title}: {error_msg}")

            classified_step = classify_youtube_error(error_msg)

            # Phase 3 (failure): the classified step and the error detail land together.
            with self.uow_factory() as uow:
                content.error_info = error_msg
                content.step = classified_step
                uow.contents.update_content(content)
                uow.commit()

            # Only an unclassified failure can be a bot block. A recognised
            # per-video restriction (age, members-only, removed, private) is
            # terminal for that video alone and must not abort the batch.
            if classified_step is ContentStep.ERROR and is_bot_block(error_msg):
                self.logger.critical(
                    "YouTube bot block detected! Aborting download job."
                )
                raise

            return True

        # Create the storage path format (/youtube/canal/arquivo.ext)
        storage_path = format_storage_path(
            content.origin or "", os.path.basename(final_file_path)
        )

        # Phase 3 (success): the file path and both remaining steps commit as a unit.
        # DOWNLOADED is written before COMPLETED so the step history keeps recording
        # the transition, but a crash can no longer strand the row on DOWNLOADED.
        with self.uow_factory() as uow:
            content.file_path = storage_path
            content.step = ContentStep.DOWNLOADED
            content = uow.contents.update_content(content)

            content.step = ContentStep.COMPLETED
            uow.contents.update_content(content)
            uow.commit()

        self.logger.info(
            f"Successfully downloaded: {content.title} to {storage_path}"
        )
        return True
