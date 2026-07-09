from datetime import datetime, timezone

from src.application.interfaces.ilogger import ILogger
from src.domain.interfaces.content_repository import IContentRepository
from src.domain.interfaces.monitor_service import IMonitorTaskService
from src.domain.interfaces.monitored_source_repository import IMonitoredSourceRepository
from src.domain.interfaces.scraper import IYouTubeScraper
from src.domain.models.content_entity import ContentEntity
from src.domain.models.enums.content_status import ContentStatus
from src.domain.models.enums.source_platform import SourcePlatform
from src.domain.models.source_entity import SourceEntity


class MonitorTaskService(IMonitorTaskService):
    """Service responsible for running background monitoring routines."""

    def __init__(
            self,
            youtube_scraper: IYouTubeScraper,
            monitored_source_repository: IMonitoredSourceRepository,
            content_repository: IContentRepository,
            logger: ILogger,
    ):
        self.youtube_scraper = youtube_scraper
        self.monitored_source_repository = monitored_source_repository
        self.content_repository = content_repository
        self.logger = logger
        self.scrapers = {
            SourcePlatform.YOUTUBE: self.youtube_scraper.extract_channel_videos,
        }

    def process_source(self, source: SourceEntity) -> int:
        """Processes a single source and returns the number of new contents."""
        scraper_func = self.scrapers.get(source.source_platform)
        if not scraper_func:
            self.logger.error(f"No scraper available for: {source.source_platform}", context={"source_platform": source.source_platform})
            return 0

        self.logger.debug(f"🔍 Checking: {source.name} ({source.source_platform})", context={"source_name": source.name, "source_platform": source.source_platform})

        # Execute extraction using the scraper interface
        try:
            items = scraper_func(source.url)
        except Exception as e:
            self.logger.error(f"Error extracting {source.url}: {e}", context={"url": source.url, "error": str(e)})
            return 0

        self.logger.debug(f"  Contents found: {len(items)}", context={"items_count": len(items)})

        new_count = 0
        for item in items:
            exists = self.content_repository.exists_by_external_id(item.id)
            if exists:
                continue

            new_item = ContentEntity(
                external_id=item.id,
                title=item.title or "Untitled",
                url=item.url,
                source_platform=source.source_platform,
                origin=source.name,
                status=ContentStatus.PENDING_DOWNLOAD,
            )
            self.content_repository.create(new_item)
            new_count += 1

        # Update last_checked_at
        source.last_checked_at = datetime.now(timezone.utc)
        self.monitored_source_repository.update(source)

        return new_count

    def daily_capture_routine(self):
        """Checks ALL active channels sequentially, one at a time."""
        self.logger.debug("🌙 Starting daily check of all channels...")

        try:
            sources = self.monitored_source_repository.get_all_active()

            if not sources:
                self.logger.warning("⚠️ No active source registered.")
                return

            self.logger.debug(f"📋 {len(sources)} source(s) to check.", context={"source_count": len(sources)})

            total_new = 0
            for i, source in enumerate(sources, start=1):
                try:
                    new_count = self.process_source(source)
                    total_new += new_count
                    self.logger.debug(f"  ✅ [{i}/{len(sources)}] {source.name}: {new_count} new", context={"source_name": source.name, "new_count": new_count})
                except Exception as e:
                    self.logger.error(f"  ❌ [{i}/{len(sources)}] {source.name}: {e}", context={"source_name": source.name, "error": str(e)})

            self.logger.debug(f"🏁 Check completed! Total new contents: {total_new}", context={"total_new": total_new})
        except Exception as e:
            self.logger.error(f"Unexpected error in daily routine: {e}", context={"error": str(e)})

