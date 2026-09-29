from pydantic import Field, SecretStr
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

    # Required on purpose. While it was optional, an unset value travelled all the way
    # into yt-dlp as None and blew up on os.path.join when a download started, which is
    # a slow and confusing way to find out the variable is missing.
    DOWNLOAD_YOUTUBE_PATH: str

    LIST_LOG_LEVELS: str | None = None

    # Optional: the notification degrades to a warning when either is missing.
    VOICE_MONKEY_API_TOKEN: str | None = None
    VOICE_MONKEY_NEW_VIDEO_FOR_DOWNLOAD_MONKEY_ID: str | None = None

    DIARIZATION_API_URL: str | None = "http://localhost:8001"

    # Directory containing the ffmpeg binaries. Leave unset when ffmpeg is on PATH,
    # which is the case inside the container: yt-dlp then locates it on its own. It only
    # needs a value on a host where ffmpeg is installed somewhere yt-dlp cannot find.
    FFMPEG_LOCATION: str | None = None

    # Comma-separated list of browser origins allowed to call the API. Declared as a
    # string, like LIST_LOG_LEVELS, because pydantic-settings expects JSON for list
    # fields, which is awkward to write in a .env file.
    #
    # The default only covers local development. Deployments that serve a frontend from
    # another host have to set this explicitly.
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"
    ADMIN_API_KEY: SecretStr | None = None
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
