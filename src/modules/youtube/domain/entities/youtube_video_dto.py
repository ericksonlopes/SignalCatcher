from typing import Optional

from pydantic import BaseModel


class YouTubeVideoDTO(BaseModel):
    """The video data the scraper port returns.

    Despite the "DTO" suffix, this belongs to the domain: `IYouTubeScraper` is a domain
    port and this is part of its contract. Moving it into `application/dtos` would make
    the domain layer import from the application layer, inverting the dependency.
    """

    id: str
    title: Optional[str] = None
    url: str
    channel: Optional[str] = None
