from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Ignore unrelated variables present in the environment instead of failing.
        extra="ignore",
    )

    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DATABASE: str
    POSTGRES_HOST: str

    DOWNLOAD_YOUTUBE_PATH: str
    GOOGLE_DRIVE_OAUTH_PATH: str = "./drive-auth/token.json"
    GOOGLE_DRIVE_CLIENT_JSON_PATH: str = "./drive-auth/client.json"
    GOOGLE_DRIVE_OAUTH_REDIRECT_URI: str = (
        "http://eriberry.local:3000/api/youtube/drive-oauth/callback"
    )
    GOOGLE_DRIVE_FOLDER_ID: str = "15UskOqNHVgjXmeN1URSf8ZP300GM-BSu"

    LIST_LOG_LEVELS: str | None = None

    VOICE_MONKEY_API_TOKEN: str | None = None
    VOICE_MONKEY_NEW_VIDEO_FOR_DOWNLOAD_MONKEY_ID: str | None = None

    DIARIZATION_API_URL: str | None = "http://localhost:8001"
    FFMPEG_LOCATION: str | None = None

    CORS_ALLOWED_ORIGINS: str = (
        "http://localhost:3000,http://localhost:5173,http://eriberry.local:3000/"
    )
    PROCESSING_LEASE_SECONDS: int = Field(default=300, ge=60)
    MAX_PROCESSING_ATTEMPTS: int = Field(default=5, ge=1, le=100)
    RETRY_BASE_SECONDS: int = Field(default=300, ge=1)
    RETRY_MAX_SECONDS: int = Field(default=86400, ge=1)
    DIARIZATION_CONNECT_TIMEOUT: float = Field(default=10, gt=0)
    DIARIZATION_READ_TIMEOUT: float = Field(default=300, gt=0)
    WORKER_HEARTBEAT_MAX_AGE: int = Field(default=60, ge=10)

    @property
    def database_url(self) -> str:
        return URL.create(
            "postgresql+psycopg2",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=5432,
            database=self.POSTGRES_DATABASE,
        ).render_as_string(hide_password=False)

    @property
    def cors_origin_list(self) -> list[str]:
        # A browser's Origin header never has a trailing slash, and CORS matching is
        # exact, so "http://host:3000/" would never match. Strip it here so a stray
        # slash in the env var does not silently break every request.
        return [
            origin.strip().rstrip("/")
            for origin in self.CORS_ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ]


settings = Settings()
