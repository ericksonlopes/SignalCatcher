from src.modules.youtube.domain.enums.content_step import ContentStep


def classify_youtube_error(error_msg: str) -> ContentStep:
    """Maps a YouTube error message to the appropriate ContentStep.

    Centralizes the error classification logic used across multiple use cases
    to avoid duplication.
    """
    error_lower = error_msg.lower()

    if "this video has been removed" in error_lower or "this video is unavailable" in error_lower:
        return ContentStep.VIDEO_REMOVED
    elif (
        "members-only content like this video" in error_lower
        or "members on level" in error_lower
    ):
        return ContentStep.MEMBERS_ONLY
    elif "sign in to confirm your age" in error_lower:
        return ContentStep.AGE_RESTRICTED
    elif (
        "private video" in error_lower
        and "sign in if you've been granted access" in error_lower
    ):
        return ContentStep.PRIVATE_VIDEO
    elif "removed following a copyright" in error_lower:
        return ContentStep.COPYRIGHT_REMOVED
    elif "account associated with this video has been terminated" in error_lower:
        return ContentStep.ACCOUNT_TERMINATED
    elif (
        "premieres in" in error_lower
        or "premiere will begin" in error_lower
        or "this live event will begin in" in error_lower
        or "this live event will begin" in error_lower
        or "this video will be available" in error_lower
    ):
        # Scheduled premiere / upcoming live: not terminal. The video becomes
        # downloadable once it airs, so it is retried later instead of erroring.
        return ContentStep.SCHEDULED
    else:
        return ContentStep.ERROR


def is_bot_block(error_msg: str) -> bool:
    """Checks if the error indicates YouTube bot detection.

    When True, the caller should stop all operations to avoid IP bans.

    Only the "not a bot" wording counts. Matching the broader "sign in to confirm"
    prefix would also match "Sign in to confirm your age", which is an ordinary
    per-video restriction and must not abort the whole batch. The apostrophe is left
    out of the marker because YouTube renders it as both ' and ’.
    """
    return "not a bot" in error_msg.lower()
