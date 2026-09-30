from collections.abc import Callable

from src.core.logger.interfaces import ILogger
from src.modules.youtube.application.use_cases.jobs.content_lease import ContentLease
from src.modules.youtube.application.use_cases.jobs.metadata import apply_metadata
from src.modules.youtube.domain.enums.content_step import ContentStep
from src.modules.youtube.domain.error_classifier import classify_youtube_error, is_bot_block
from src.modules.youtube.domain.interfaces.services.scraper import IYouTubeScraper
from src.modules.youtube.domain.interfaces.unit_of_work import IYoutubeUnitOfWork
from src.modules.youtube.domain.processing import LeaseLostError


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
        with self.uow_factory() as uow:
            count = uow.contents.reset_stuck_steps(
                ContentStep.EXTRACTING_METADATA, ContentStep.PENDING_METADATA_EXTRACTION
            )
            uow.commit()
        return count

    def execute(
        self,
        steps: list[ContentStep] | None = None,
        exclude_ids: set[str] | None = None,
        external_id: str | None = None,
    ) -> str | None:
        with self.uow_factory() as uow:
            content = uow.contents.claim_next(
                steps or [ContentStep.PENDING_METADATA_EXTRACTION],
                ContentStep.EXTRACTING_METADATA,
                exclude_ids=exclude_ids,
                external_id=external_id,
            )
            uow.commit()
        if content is None:
            return None
        with ContentLease(self.uow_factory, content, self.logger) as lease:
            try:
                metadata = self.youtube_scraper.extract_metadata(content.url)
                lease.ensure_owned()
                channel = apply_metadata(content, metadata)
                content.error_info = None
                with self.uow_factory() as uow:
                    # Check ownership before changing another aggregate.
                    content.step = ContentStep.METADATA_EXTRACTED
                    content = uow.contents.update_content(content)
                    if channel:
                        uow.channels.upsert_channel(channel)
                    content.step = ContentStep.PENDING_DOWNLOAD
                    uow.contents.update_content(content)
                    uow.commit()
            except LeaseLostError:
                raise
            except Exception as exc:
                lease.ensure_owned()
                content.error_info = str(exc)
                content.step = classify_youtube_error(str(exc))
                with self.uow_factory() as uow:
                    uow.contents.update_content(content)
                    uow.commit()
                if content.step is ContentStep.SCHEDULED:
                    self.logger.warning(
                        f"Video {content.external_id} is not available yet; "
                        "waiting for its premiere or live event. Metadata extraction deferred.",
                        context={"reason": str(exc), "step": content.step.value},
                    )
                else:
                    self.logger.error(
                        f"Metadata extraction failed for {content.external_id}: {exc}"
                    )
                if content.step is ContentStep.ERROR and is_bot_block(str(exc)):
                    raise
        return content.external_id
