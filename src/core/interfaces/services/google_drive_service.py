from abc import ABC, abstractmethod
from typing import Any


class IGoogleDriveService(ABC):
    """
    Base interface for Google Drive operations.
    """

    @abstractmethod
    def list_items(self, folder_id: str | None = None, page_size: int = 50) -> list[dict[str, Any]]:
        """Lists files and folders from Google Drive."""
        pass

    @abstractmethod
    def get_folders(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filters the items list to return only folders."""
        pass

    @abstractmethod
    def get_files(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filters the items list to return only files."""
        pass
