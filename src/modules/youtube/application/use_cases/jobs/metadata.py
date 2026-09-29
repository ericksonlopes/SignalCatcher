from datetime import datetime, timezone

from src.modules.youtube.domain.entities.youtube_content_entity import YoutubeContentEntity


def apply_metadata(content: YoutubeContentEntity, metadata: dict) -> dict | None:
    """Keep metadata extraction and retries on the same mapping path."""
    content.raw_metadata = metadata
    content.title = metadata.get("title") or content.title
    content.language = metadata.get("language") or content.language
    content.thumbnail = metadata.get("thumbnail")
    duration = metadata.get("duration")
    content.duration = int(duration) if duration is not None else None
    content.categories = metadata.get("categories") or []
    content.tags = metadata.get("tags") or []
    if metadata.get("timestamp"):
        content.published_at = datetime.fromtimestamp(int(metadata["timestamp"]), timezone.utc)
    elif metadata.get("upload_date"):
        content.published_at = datetime.strptime(metadata["upload_date"], "%Y%m%d")
    uploader_id = metadata.get("uploader_id")
    if not uploader_id:
        return None
    channel_id = uploader_id.lstrip("@")
    # Preserve the optional playlist directory while updating the channel handle.
    _, separator, playlist = content.origin.partition("/")
    content.origin = channel_id + (separator + playlist if separator else "")
    return {
        "id": channel_id,
        "title": metadata.get("uploader") or metadata.get("channel"),
        "url": metadata.get("channel_url"),
        "channel_url": metadata.get("uploader_url") or metadata.get("channel_url"),
        "thumbnails": [],
    }
