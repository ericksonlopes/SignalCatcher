import os
from typing import List, Dict, Any, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from src.core.interfaces.services.google_drive_service import IGoogleDriveService

class GoogleDriveService(IGoogleDriveService):
    """Service class for interacting with Google Drive via Service Account."""
    
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    
    def __init__(self, credentials_path: str = "service_account.json"):
        self.credentials_path = credentials_path
        self._service = self._authenticate()

    def _authenticate(self):
        """Authenticates and returns the Google Drive API service instance."""
        if not os.path.exists(self.credentials_path):
            raise FileNotFoundError(
                f"Google Drive service account credentials not found at: {self.credentials_path}"
            )
            
        creds = service_account.Credentials.from_service_account_file(
            self.credentials_path, scopes=self.SCOPES
        )
        return build('drive', 'v3', credentials=creds)
        
    def list_items(self, folder_id: Optional[str] = None, page_size: int = 50) -> List[Dict[str, Any]]:
        """
        Lists files and folders from Google Drive.
        If folder_id is provided, it lists items inside that specific folder.
        """
        query = "trashed=false"
        if folder_id:
            query += f" and '{folder_id}' in parents"
            
        results = self._service.files().list(
            q=query,
            pageSize=page_size,
            fields="nextPageToken, files(id, name, mimeType)"
        ).execute()
        
        return results.get('files', [])
        
    def get_folders(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filters the items list to return only folders."""
        return [item for item in items if item.get('mimeType') == 'application/vnd.google-apps.folder']
        
    def get_files(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filters the items list to return only files."""
        return [item for item in items if item.get('mimeType') != 'application/vnd.google-apps.folder']
