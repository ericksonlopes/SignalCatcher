from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

from src.core.logger.interfaces import ILogger
from src.modules.youtube.domain.entities.channel_entity import ChannelEntity
from src.modules.youtube.domain.interfaces.services.monitor_service import (
    IMonitorTaskService,
)
from src.modules.youtube.domain.interfaces.services.scraper import IYouTubeScraper
from src.modules.youtube.domain.interfaces.unit_of_work import IYoutubeUnitOfWork


class MonitorTaskService(IMonitorTaskService):
    """Service responsible for running background monitoring routines."""

    def __init__(
        self,
        youtube_scraper: IYouTubeScraper,
        uow_factory: Callable[[], IYoutubeUnitOfWork],
        logger: ILogger,
    ):
        self.youtube_scraper = youtube_scraper
        self.uow_factory = uow_factory
        self.logger = logger
        # Only YouTube is supported now, so we always use the youtube scraper
        self.scraper_func = self.youtube_scraper.extract_channel_videos

    def process_channel(self, channel: ChannelEntity) -> int:
        """Processes a single channel and returns the number of new contents."""
        self.logger.debug(
            f"🔍 Checking: {channel.name}", context={"channel_name": channel.name}
        )

        # Execute extraction using the scraper interface, outside any transaction.
        try:
            items = self.scraper_func(channel.url)
        except Exception as e:
            self.logger.error(
                f"Error extracting {channel.url}: {e}",
                context={"url": channel.url, "error": str(e)},
            )
            return 0

        self.logger.debug(
            f"  Contents found: {len(items)}", context={"items_count": len(items)}
        )

        # The new contents and the channel's last_checked_at commit as a unit. Before,
        # each content committed on its own and last_checked_at committed separately,
        # so a failure midway advanced the watermark for only part of the channel.
        new_count = 0
        with self.uow_factory() as uow:
            for item in items:
                if uow.contents.exists_by_external_id(item.id):
                    continue

                uow.contents.add_new_content(
                    external_id=item.id,
                    title=item.title or "Untitled",
                    url=item.url,
                    origin=channel.external_id,
                )
                new_count += 1

            # Update last_checked_at
            channel.last_checked_at = datetime.now(
                ZoneInfo("America/Sao_Paulo")
            ).replace(tzinfo=None)
            uow.monitored_channels.update(channel)
            uow.commit()

        return new_count

    def daily_capture_routine(self) -> int:
        """Checks ALL active channels sequentially, one at a time and returns new items count."""
        self.logger.debug("🌙 Starting daily check of all channels...")

        try:
            with self.uow_factory() as uow:
                channels = uow.monitored_channels.get_all_active()

            if not channels:
                self.logger.warning("⚠️ No active channel registered.")
                return 0

            self.logger.debug(
                f"📋 {len(channels)} channel(s) to check.",
                context={"channel_count": len(channels)},
            )

            total_new = 0
            for i, channel in enumerate(channels, start=1):
                try:
                    new_count = self.process_channel(channel)
                    total_new += new_count
                    self.logger.debug(
                        f"  ✅ [{i}/{len(channels)}] {channel.name}: {new_count} new",
                        context={"channel_name": channel.name, "new_count": new_count},
                    )
                except Exception as e:
                    self.logger.error(
                        f"  ❌ [{i}/{len(channels)}] {channel.name}: {e}",
                        context={"channel_name": channel.name, "error": str(e)},
                    )

            self.logger.debug(
                f"🏁 Check completed! Total new contents: {total_new}",
                context={"total_new": total_new},
            )
            return total_new
        except Exception as e:
            self.logger.error(
                f"Unexpected error in daily routine: {e}", context={"error": str(e)}
            )
            return 0
