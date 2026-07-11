import enum


class ContentStatus(str, enum.Enum):
    """Content status in the download pipeline."""
    PENDING_DOWNLOAD = "PENDING_DOWNLOAD"
    DOWNLOADING = "DOWNLOADING"
    DOWNLOADED = "DOWNLOADED"
    ERROR = "ERROR"
    MEMBERS_ONLY = "MEMBERS_ONLY"
    AGE_RESTRICTED = "AGE_RESTRICTED"
    PRIVATE_VIDEO = "PRIVATE_VIDEO"
