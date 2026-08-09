from pydantic import BaseModel

class YouTubePlaylistAddRequest(BaseModel):
    url: str
    save_in_playlist_folder: bool = False
