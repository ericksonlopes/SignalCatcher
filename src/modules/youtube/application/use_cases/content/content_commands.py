from src.modules.youtube.domain.interfaces.services.youtube_content_service import (
    IYoutubeContentService,
)


class ContentCommands:
    def __init__(self, service: IYoutubeContentService):
        self.service = service

    def set_reprocessing(self, external_id: str) -> bool:
        return self.service.request_reprocessing(external_id)

    def delete_content(self, external_id: str) -> bool:
        """Queue an idempotent deletion; the worker confirms the physical result."""
        return self.service.request_deletion(external_id)
