from pydantic import BaseModel


class YouTubeVideoDTO(BaseModel):
    """The video data the scraper port returns.

    Despite the "DTO" suffix, this belongs to the domain: `IYouTubeScraper` is a domain
    port and this is part of its contract. Moving it into `application/dtos` would make
    the domain layer import from the application layer, inverting the dependency.
    """

    id: str
    title: str | None = None
    url: str
    channel: str | None = None
