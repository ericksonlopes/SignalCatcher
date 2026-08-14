from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DATABASE: str
    POSTGRES_HOST: str
    LIST_LOG_LEVELS: Optional[str] = None
    VOICE_MONKEY_API_TOKEN: Optional[str] = None
    VOICE_MONKEY_NEW_VIDEO_FOR_DOWNLOAD_MONKEY_ID: Optional[str] = None
    DOWNLOAD_YOUTUBE_PATH: Optional[str] = None
    DIARIZATION_API_URL: Optional[str] = "http://localhost:8001"

    @property
    def database_url(self) -> str:
        from urllib.parse import quote_plus
        encoded_password = quote_plus(self.POSTGRES_PASSWORD)
        return (f"postgresql+psycopg2://"
                f"{self.POSTGRES_USER}:"
                f"{encoded_password}@"
                f"{self.POSTGRES_HOST}:5432/"
                f"{self.POSTGRES_DATABASE}"
                )

    class Config:
        env_file = ".env"


settings = Settings()
