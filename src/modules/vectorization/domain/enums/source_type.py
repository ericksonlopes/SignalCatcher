from enum import Enum


class SourceType(str, Enum):
    YOUTUBE_TRANSCRIPT = "YOUTUBE_TRANSCRIPT"
    DOCUMENT = "DOCUMENT"
    WEBSITE = "WEBSITE"
    CUSTOM = "CUSTOM"
