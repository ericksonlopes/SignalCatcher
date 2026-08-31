import datetime
from collections.abc import Callable

from src.core.logger.interfaces import ILogger
from src.modules.youtube.domain.entities.youtube_content_entity import (
    YoutubeContentEntity,
)
from src.modules.youtube.domain.enums.content_step import ContentStep
from src.modules.youtube.domain.error_classifier import (
    classify_youtube_error,
    is_bot_block,
)
from src.modules.youtube.domain.interfaces.services.scraper import IYouTubeScraper
from src.modules.youtube.domain.interfaces.unit_of_work import IYoutubeUnitOfWork


class ExtractMetadataUseCase:

    def __init__(
        self,
        uow_factory: Callable[[], IYoutubeUnitOfWork],
        youtube_scraper: IYouTubeScraper,
        logger: ILogger,
    ):
        self.uow_factory = uow_factory
        self.youtube_scraper = youtube_scraper
        self.logger = logger

    def reset_stuck_items(self) -> int:
        """Resets items stuck in EXTRACTING_METADATA back to PENDING_METADATA_EXTRACTION.

        Should be called before starting the extraction loop to recover from a run that
        was killed outright, which is the one case a transaction cannot undo.
        """
        with self.uow_factory() as uow:
            count = uow.contents.reset_stuck_steps(
                stuck_step=ContentStep.EXTRACTING_METADATA,
                pending_step=ContentStep.PENDING_METADATA_EXTRACTION,
            )
            uow.commit()
        return count

    def execute(self) -> bool:
        """
        Executes one pending metadata extraction.
        Returns True if a content was processed, False if there are no pending contents.

        The work is split into phases with their own transactions. The scrape is a
        network call and runs between them, so no transaction is held open across it.
        """
        # Phase 1: claim one pending content and commit, so EXTRACTING_METADATA is
        # visible while the scrape runs.
        with self.uow_factory() as uow:
            content = uow.contents.get_first_by_step(
                ContentStep.PENDING_METADATA_EXTRACTION
            )

            if not content:
                return False

            self.logger.info(
                f"Extracting metadata for content: {content.title} ({content.url})"
            )

            content.step = ContentStep.EXTRACTING_METADATA
            content = uow.contents.update_content(content)
            uow.commit()

        try:
            # Phase 2: the scrape, outside any transaction.
            metadata_dict = self.youtube_scraper.extract_metadata(content.url)

            content.raw_metadata = metadata_dict
            content.thumbnail = metadata_dict.get("thumbnail")

            duration_seconds = metadata_dict.get("duration")
            if duration_seconds is not None:
                content.duration = int(duration_seconds)

            content.categories = metadata_dict.get("categories")
            content.tags = metadata_dict.get("tags")

            timestamp = metadata_dict.get("timestamp")
            if timestamp:
                content.published_at = datetime.datetime.fromtimestamp(
                    int(timestamp), tz=datetime.timezone.utc
                )

            # Update channel and content origin using external_id (handle)
            uploader_id = metadata_dict.get("uploader_id")
            channel_info: dict | None = None
            if uploader_id:
                external_id = uploader_id.lstrip("@")

                channel_info = {
                    "id": external_id,
                    "title": metadata_dict.get("uploader")
                    or metadata_dict.get("channel"),
                    "description": metadata_dict.get(
                        "description"
                    ),  # Might be video description, but better than nothing or we can skip description
                    "url": metadata_dict.get("channel_url"),
                    "channel_url": metadata_dict.get("uploader_url")
                    or metadata_dict.get("channel_url"),
                    "thumbnails": [],  # Channel thumbnails aren't usually in video metadata_dict, but that's fine
                }

                # Update origin
                content.origin = external_id

            # Phase 3: the channel upsert, the extracted metadata and both remaining
            # steps land as a unit. METADATA_EXTRACTED is written before
            # PENDING_DOWNLOAD so the step history keeps recording the transition,
            # but a crash can no longer strand the row on either of them. Previously
            # the upsert committed separately from the origin that points at it.
            with self.uow_factory() as uow:
                if channel_info is not None:
                    uow.channels.upsert_channel(channel_info)

                content.step = ContentStep.METADATA_EXTRACTED
                content = uow.contents.update_content(content)

                content.step = ContentStep.PENDING_DOWNLOAD
                uow.contents.update_content(content)
                uow.commit()

            self.logger.info(f"Successfully extracted metadata for: {content.title}")

        except Exception as e:
            error_msg = str(e)
            self.logger.error(
                f"Error extracting metadata for {content.title}: {error_msg}"
            )

            classified_step = classify_youtube_error(error_msg)
            self._record_failure(content, error_msg, classified_step)

            # If YouTube blocked our IP, we must abort the entire job loop to avoid
            # hammering them. Only an unclassified failure qualifies: a recognised
            # per-video restriction is terminal for that video alone.
            if classified_step is ContentStep.ERROR and is_bot_block(error_msg):
                self.logger.critical(
                    "YouTube bot block detected! Pausing scheduler job."
                )
                raise e

        return True

    def _record_failure(
        self,
        content: YoutubeContentEntity,
        error_msg: str,
        classified_step: ContentStep,
    ) -> None:
        """Stores the classified step and the error detail in a single transaction."""
        with self.uow_factory() as uow:
            content.error_info = error_msg
            content.step = classified_step
            uow.contents.update_content(content)
            uow.commit()
