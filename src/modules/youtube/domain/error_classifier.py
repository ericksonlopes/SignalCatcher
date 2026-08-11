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
    else:
        return ContentStep.ERROR


def is_bot_block(error_msg: str) -> bool:
    """Checks if the error indicates YouTube bot detection.

    When True, the caller should stop all operations to avoid IP bans.
    """
    error_lower = error_msg.lower()
    return (
        "sign in to confirm you're not a bot" in error_lower
        or "sign in to confirm" in error_lower
    )
