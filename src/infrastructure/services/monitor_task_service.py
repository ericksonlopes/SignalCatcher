from datetime import datetime
from zoneinfo import ZoneInfo

from src.domain.interfaces.logger import ILogger
from src.domain.interfaces.youtube_content_repository import IYoutubeContentRepository
from src.domain.interfaces.monitor_service import IMonitorTaskService
from src.domain.interfaces.youtube_monitored_channel_repository import IYouTubeMonitoredChannelRepository
from src.domain.interfaces.scraper import IYouTubeScraper
from src.domain.models.youtube_content_entity import YoutubeContentEntity
from src.domain.models.enums.content_step import ContentStep
from src.domain.models.channel_entity import ChannelEntity


class MonitorTaskService(IMonitorTaskService):
    """Service responsible for running background monitoring routines."""

    def __init__(
            self,
            youtube_scraper: IYouTubeScraper,
            youtube_monitored_channel_repository: IYouTubeMonitoredChannelRepository,
            youtube_content_repository: IYoutubeContentRepository,
            logger: ILogger,
    ):
        self.youtube_scraper = youtube_scraper
        self.youtube_monitored_channel_repository = youtube_monitored_channel_repository
        self.youtube_content_repository = youtube_content_repository
        self.logger = logger
        # Only YouTube is supported now, so we always use the youtube scraper
        self.scraper_func = self.youtube_scraper.extract_channel_videos

    def process_channel(self, channel: ChannelEntity) -> int:
        """Processes a single channel and returns the number of new contents."""
        self.logger.debug(f"🔍 Checking: {channel.name}", context={"channel_name": channel.name})

        # Execute extraction using the scraper interface
        try:
            items = self.scraper_func(channel.url)
        except Exception as e:
            self.logger.error(f"Error extracting {channel.url}: {e}", context={"url": channel.url, "error": str(e)})
            return 0

        self.logger.debug(f"  Contents found: {len(items)}", context={"items_count": len(items)})

        new_count = 0
        for item in items:
            exists = self.youtube_content_repository.exists_by_external_id(item.id)
            if exists:
                continue

            new_item = YoutubeContentEntity(
                external_id=item.id,
                title=item.title or "Untitled",
                url=item.url,
                origin=channel.name,
                step=ContentStep.PENDING_DOWNLOAD,
            )
            self.youtube_content_repository.create(new_item)
            new_count += 1

        # Update last_checked_at
        channel.last_checked_at = datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
        self.youtube_monitored_channel_repository.update(channel)

        return new_count

    def daily_capture_routine(self) -> int:
        """Checks ALL active channels sequentially, one at a time and returns new items count."""
        self.logger.debug("🌙 Starting daily check of all channels...")

        try:
            channels = self.youtube_monitored_channel_repository.get_all_active()

            if not channels:
                self.logger.warning("⚠️ No active channel registered.")
                return 0

            self.logger.debug(f"📋 {len(channels)} channel(s) to check.", context={"channel_count": len(channels)})

            total_new = 0
            for i, channel in enumerate(channels, start=1):
                try:
                    new_count = self.process_channel(channel)
                    total_new += new_count
                    self.logger.debug(f"  ✅ [{i}/{len(channels)}] {channel.name}: {new_count} new", context={"channel_name": channel.name, "new_count": new_count})
                except Exception as e:
                    self.logger.error(f"  ❌ [{i}/{len(channels)}] {channel.name}: {e}", context={"channel_name": channel.name, "error": str(e)})

            self.logger.debug(f"🏁 Check completed! Total new contents: {total_new}", context={"total_new": total_new})
            return total_new
        except Exception as e:
            self.logger.error(f"Unexpected error in daily routine: {e}", context={"error": str(e)})
            return 0

