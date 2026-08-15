from src.modules.youtube.domain.interfaces.services.youtube_content_service import (
    IYoutubeContentService,
)


class ContentQueries:
    def __init__(self, service: IYoutubeContentService):
        self.service = service

    def get_status_count(self):
        return self.service.count_by_step()

    def get_tracking(self, external_id: str):
        if not self.service.exists_by_external_id(external_id):
            return None
        return self.service.get_tracking_by_external_id(external_id)

    def get_contents(
        self, page: int, limit: int, step: str | None = None, search: str | None = None, channel: str | None = None
    ):
        return self.service.get_paginated(page, limit, step, search, channel)


    def get_content_by_external_id(self, external_id: str):
        return self.service.get_by_external_id(external_id)
