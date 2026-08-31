class YoutubeError(Exception):
    """Base class for errors raised by the youtube module."""


class ScraperError(YoutubeError):
    """Raised when the scraper cannot extract or download the requested content."""
