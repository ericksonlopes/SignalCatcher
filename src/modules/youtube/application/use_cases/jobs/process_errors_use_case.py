import datetime
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
        """Retries processing all videos currently in ERROR or REPROCESSING step.

        Returns the number of videos attempted.
        Raises Exception if YouTube bot detection is triggered.

        Each attempt uses its own short transactions, so one failing video never
        rolls back the outcome already recorded for the previous ones.
        """
        retried_count = 0
        tried_ids: set[str] = set()

        while True:
            # Claim the next errored or reprocessing video and mark it in progress.
            with self.uow_factory() as uow:
                content = uow.contents.get_first_by_step(ContentStep.ERROR)
                if not content:
                    content = uow.contents.get_first_by_step(ContentStep.REPROCESSING)

                if not content or content.external_id in tried_ids:
                    break

                tried_ids.add(content.external_id)
                self.logger.info(f"Retrying content: {content.title} ({content.url})")
                if content.error_info:
                    self.logger.warning(f"Previous Error: {content.error_info}")

                content.step = ContentStep.EXTRACTING_METADATA
                content = uow.contents.update_content(content)
                uow.commit()

            retried_count += 1

            try:
                # Phase 1: extract metadata, outside any transaction.
                self.logger.info(
                    f"Reprocessing {content.title}: Extracting metadata..."
                )
                info_dict = self.scraper.extract_metadata(content.url)

                channel_info = None
                if info_dict:
                    content.raw_metadata = info_dict
                    content.thumbnail = info_dict.get("thumbnail")

                    duration_sec = info_dict.get("duration")
                    if duration_sec is not None:
                        content.duration = int(duration_sec)

                    content.categories = info_dict.get("categories", [])
                    content.tags = info_dict.get("tags", [])

                    pub_date_str = info_dict.get("upload_date")
                    if pub_date_str and len(pub_date_str) == 8:
                        content.published_at = datetime.datetime.strptime(
                            pub_date_str, "%Y%m%d"
                        )
                    elif info_dict.get("timestamp"):
                        content.published_at = datetime.datetime.fromtimestamp(
                            int(info_dict["timestamp"]), tz=datetime.timezone.utc
                        )

                    uploader_id = info_dict.get("uploader_id")
                    if uploader_id:
                        external_id = uploader_id.lstrip("@")
                        channel_info = {
                            "id": external_id,
                            "title": info_dict.get("uploader")
                            or info_dict.get("channel"),
                            "description": info_dict.get("description"),
                            "url": info_dict.get("channel_url"),
                            "channel_url": info_dict.get("uploader_url")
                            or info_dict.get("channel_url"),
                            "thumbnails": [],
                        }
                        content.origin = external_id

                # The extracted metadata and the move into DOWNLOADING commit together.
                with self.uow_factory() as uow:
                    if channel_info is not None:
                        uow.channels.upsert_channel(channel_info)

                    content.step = ContentStep.DOWNLOADING
                    content = uow.contents.update_content(content)
                    uow.commit()

                # Phase 2: download, outside any transaction.
                self.logger.info(f"Reprocessing {content.title}: Downloading...")
                final_file_path = self.scraper.download_video(
                    url=content.url,
                    content_id=content.external_id,
                    origin=content.origin,
                    output_path=self.output_path,
                )

                storage_path = format_storage_path(
                    content.origin or "", os.path.basename(final_file_path)
                )

                # Phase 3: finished - the final step and the cleared error commit together.
                with self.uow_factory() as uow:
                    content.file_path = storage_path
                    content.step = ContentStep.COMPLETED
                    content.error_info = None
                    uow.contents.update_content(content)
                    uow.commit()

                self.logger.info(
                    f"Successfully reprocessed: {content.title} to {storage_path}"
                )

            except Exception as e:
                error_msg = str(e)
                self.logger.error(
                    f"Error reprocessing {content.title}: {error_msg}"
                )

                classified_step = classify_youtube_error(error_msg)

                with self.uow_factory() as uow:
                    content.error_info = error_msg
                    content.step = classified_step
                    uow.contents.update_content(content)
                    uow.commit()

                # Only an unclassified failure can be a bot block.
                if classified_step is ContentStep.ERROR and is_bot_block(error_msg):
                    self.logger.critical(
                        "YouTube bot block detected! Aborting error retry."
                    )
                    raise

        return retried_count
