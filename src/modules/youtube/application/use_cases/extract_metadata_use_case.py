import datetime

from src.core.logger.interfaces import ILogger
from src.modules.youtube.domain.interfaces.scraper import IYouTubeScraper
from src.modules.youtube.domain.interfaces.youtube_content_repository import IYoutubeContentRepository
from src.modules.youtube.domain.enums.content_step import ContentStep

from src.modules.youtube.infrastructure.repositories.youtube_channel_repository import YouTubeChannelRepository

class ExtractMetadataUseCase:
    def __init__(self, youtube_content_repository: IYoutubeContentRepository, youtube_scraper: IYouTubeScraper, youtube_channel_repository: YouTubeChannelRepository, logger: ILogger):
        self.youtube_content_repository = youtube_content_repository
        self.youtube_scraper = youtube_scraper
        self.youtube_channel_repository = youtube_channel_repository
        self.logger = logger

    def execute(self) -> bool:
        """
        Executes one pending metadata extraction.
        Returns True if a content was processed, False if there are no pending contents.
        """
        content = self.youtube_content_repository.get_first_by_step(ContentStep.PENDING_METADATA_EXTRACTION)

        if not content:
            return False

        self.logger.info(f"Extracting metadata for content: {content.title} ({content.url})")

        # Transition to EXTRACTING_METADATA
        content.step = ContentStep.EXTRACTING_METADATA
        self.youtube_content_repository.update(content)

        try:
            # Extract metadata using the scraper
            metadata_dict = self.youtube_scraper.extract_metadata(content.url)

            content.raw_metadata = metadata_dict
            content.thumbnail = metadata_dict.get('thumbnail')
            
            duration_seconds = metadata_dict.get('duration')
            if duration_seconds:
                content.duration = str(datetime.timedelta(seconds=int(duration_seconds)))
            
            content.categories = metadata_dict.get('categories')
            content.tags = metadata_dict.get('tags')

            timestamp = metadata_dict.get('timestamp')
            if timestamp:
                content.published_at = datetime.datetime.fromtimestamp(int(timestamp), tz=datetime.timezone.utc)

            # Update channel and content origin using external_id (handle)
            uploader_id = metadata_dict.get('uploader_id')
            if uploader_id:
                external_id = uploader_id.lstrip('@')
                
                channel_info = {
                    "id": external_id,
                    "title": metadata_dict.get("uploader") or metadata_dict.get("channel"),
                    "description": metadata_dict.get("description"), # Might be video description, but better than nothing or we can skip description
                    "url": metadata_dict.get("channel_url"),
                    "channel_url": metadata_dict.get("uploader_url") or metadata_dict.get("channel_url"),
                    "thumbnails": [] # Channel thumbnails aren't usually in video metadata_dict, but that's fine
                }
                
                # Upsert channel
                self.youtube_channel_repository.upsert_channel(channel_info)
                
                # Update origin
                content.origin = external_id

            # Complete step
            content.step = ContentStep.METADATA_EXTRACTED
            self.youtube_content_repository.update(content)

            content.step = ContentStep.PENDING_DOWNLOAD
            self.youtube_content_repository.update(content)
            self.logger.info(f"Successfully extracted metadata for: {content.title}")

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Error extracting metadata for {content.title}: {error_msg}")
            
            content.error_info = error_msg
            error_msg_lower = error_msg.lower()
            if "this video has been removed" in error_msg_lower:
                content.step = ContentStep.VIDEO_REMOVED
            elif "members-only content like this video" in error_msg_lower or "members on level" in error_msg_lower:
                content.step = ContentStep.MEMBERS_ONLY
            elif "sign in to confirm your age" in error_msg_lower:
                content.step = ContentStep.AGE_RESTRICTED
            elif "private video" in error_msg_lower and "sign in if you've been granted access" in error_msg_lower:
                content.step = ContentStep.PRIVATE_VIDEO
            elif "removed following a copyright" in error_msg_lower:
                content.step = ContentStep.COPYRIGHT_REMOVED
            elif "account associated with this video has been terminated" in error_msg_lower:
                content.step = ContentStep.ACCOUNT_TERMINATED
            else:
                content.step = ContentStep.ERROR
                
            self.youtube_content_repository.update(content)
            
            # If YouTube blocked our IP, we must abort the entire job loop to avoid hammering them.
            if "sign in to confirm you’re not a bot" in error_msg.lower() or "sign in to confirm" in error_msg.lower():
                self.logger.critical("YouTube bot block detected! Pausing scheduler job.")
                raise e

        return True
