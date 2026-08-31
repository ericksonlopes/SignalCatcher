from pydantic import BaseModel


class YouTubeChannelCreateRequest(BaseModel):
    """Request body for registering a channel to monitor.

    Lives next to the other request models rather than in `application/dtos`, where it
    used to sit as `YouTubeChannelCreateDTO`. It is the shape of the HTTP payload, not an
    application-level input: `ChannelCreateDTO` plays that role and carries the
    `external_id` that only the scraper can fill in.
    """

    name: str
    url: str
