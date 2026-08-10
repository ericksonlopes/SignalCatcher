from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class IGoogleDriveService(ABC):
    """
    Base interface for Google Drive operations.
    """

    @abstractmethod
    def list_items(self, folder_id: Optional[str] = None, page_size: int = 50) -> List[Dict[str, Any]]:
        """Lists files and folders from Google Drive."""
        pass

    @abstractmethod
    def get_folders(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filters the items list to return only folders."""
        pass

    @abstractmethod
    def get_files(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filters the items list to return only files."""
        pass
