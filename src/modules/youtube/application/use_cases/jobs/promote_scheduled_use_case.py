from collections.abc import Callable

from src.core.logger.interfaces import ILogger
from src.modules.youtube.domain.enums.content_step import ContentStep
from src.modules.youtube.domain.interfaces.unit_of_work import IYoutubeUnitOfWork


class PromoteScheduledUseCase:
    """Re-queues scheduled premieres / upcoming lives for download.

    A video in the SCHEDULED step is a premiere or live that had not aired yet the
    last time a download was attempted. It is not a terminal error: once it airs it
    becomes downloadable. This use case moves every SCHEDULED video back to
    PENDING_DOWNLOAD so the regular download job picks it up again.

    If the video still has not aired, the download job re-classifies it as SCHEDULED
    (via the error classifier), so it simply waits for the next run instead of piling
    up as an ERROR. This keeps premieres out of the error-retry loop entirely.
    """

    def __init__(
        self,
        uow_factory: Callable[[], IYoutubeUnitOfWork],
        logger: ILogger,
    ):
        self.uow_factory = uow_factory
        self.logger = logger

    def execute(self) -> int:
        """Promotes all SCHEDULED videos to PENDING_DOWNLOAD.

        Returns the number of videos re-queued.
        """
        with self.uow_factory() as uow:
            scheduled = uow.contents.get_all_by_step(ContentStep.SCHEDULED)

            if not scheduled:
                return 0

            for content in scheduled:
                self.logger.info(
                    f"Re-queuing scheduled video for download: "
                    f"{content.title} ({content.url})"
                )
                content.step = ContentStep.PENDING_DOWNLOAD
                content.error_info = None
                uow.contents.update_content(content)

            uow.commit()

        return len(scheduled)
