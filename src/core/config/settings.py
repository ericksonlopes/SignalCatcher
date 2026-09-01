from typing import Optional
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    LIST_LOG_LEVELS: Optional[str] = None

    # Optional: the notification degrades to a warning when either is missing.
    VOICE_MONKEY_API_TOKEN: Optional[str] = None
    VOICE_MONKEY_NEW_VIDEO_FOR_DOWNLOAD_MONKEY_ID: Optional[str] = None

    DIARIZATION_API_URL: Optional[str] = "http://localhost:8001"

    # Directory containing the ffmpeg binaries. Leave unset when ffmpeg is on PATH,
    # which is the case inside the container: yt-dlp then locates it on its own. It only
    # needs a value on a host where ffmpeg is installed somewhere yt-dlp cannot find.
    FFMPEG_LOCATION: Optional[str] = None

    # Comma-separated list of browser origins allowed to call the API. Declared as a
    # string, like LIST_LOG_LEVELS, because pydantic-settings expects JSON for list
    # fields, which is awkward to write in a .env file.
    #
    # The default only covers local development. Deployments that serve a frontend from
    # another host have to set this explicitly.
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    @property
    def database_url(self) -> str:
        encoded_password = quote_plus(self.POSTGRES_PASSWORD)
        return (f"postgresql+psycopg2://"
                f"{self.POSTGRES_USER}:"
                f"{encoded_password}@"
                f"{self.POSTGRES_HOST}:5432/"
                f"{self.POSTGRES_DATABASE}"
                )

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
