from urllib.parse import urlsplit


class LeaseLostError(RuntimeError):
    """The reservation expired or another operation owns the content."""


class ContentBusyError(ValueError):
    """An active operation prevents a conflicting content command."""


def is_youtube_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        return (
            parsed.scheme in {"http", "https"}
            and parsed.hostname in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
            and parsed.username is None
            and parsed.password is None
            and parsed.port in {None, 80, 443}
        )
    except ValueError:
        return False
