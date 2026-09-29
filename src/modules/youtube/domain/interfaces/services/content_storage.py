from typing import Protocol

from src.modules.youtube.domain.entities.youtube_content_entity import YoutubeContentEntity


class IContentStorage(Protocol):
    def delete_files(self, content: YoutubeContentEntity) -> None: ...
