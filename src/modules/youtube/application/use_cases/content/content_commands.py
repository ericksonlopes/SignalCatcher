import glob
import os
import re
from typing import Optional

from src.core.logger.interfaces import ILogger
from src.modules.youtube.domain.enums.content_step import ContentStep
from src.modules.youtube.domain.interfaces.youtube_content_service import IYoutubeContentService

class ContentCommands:
    def __init__(self, service: IYoutubeContentService, output_path: Optional[str] = None, logger: Optional[ILogger] = None):
        self.service = service
        self.output_path = output_path
        self.logger = logger

    def set_reprocessing(self, external_id: str) -> bool:
        content = self.service.get_by_external_id(external_id)
        if not content:
            return False
            
        self.service.update_content_step(content, ContentStep.REPROCESSING)
        return True

    def delete_content(self, external_id: str) -> bool:
        content = self.service.get_by_external_id(external_id)
        if not content:
            return False

        self.service.update_content_step(content, ContentStep.DELETED)

        if self.output_path and content.origin:
            parts = [re.sub(r'[\\*?:"<>|]', "_", p) for p in content.origin.split('/')]
            final_output_path = os.path.join(self.output_path, *parts)
            pattern = os.path.join(final_output_path, f"{content.external_id}_*.*")
            for file_path in glob.glob(pattern):
                try:
                    os.remove(file_path)
                    if self.logger:
                        self.logger.info(f"Deleted file: {file_path}")
                except Exception as e:
                    if self.logger:
                        self.logger.error(f"Failed to delete file {file_path}: {e}")
        return True
