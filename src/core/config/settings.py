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

    LIST_LOG_LEVELS: str | None = None

    VOICE_MONKEY_API_TOKEN: str | None = None
    VOICE_MONKEY_NEW_VIDEO_FOR_DOWNLOAD_MONKEY_ID: str | None = None

    DIARIZATION_API_URL: str | None = "http://localhost:8001"
    FFMPEG_LOCATION: str | None = None

    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"
    PROCESSING_LEASE_SECONDS: int = Field(default=300, ge=60)
    MAX_PROCESSING_ATTEMPTS: int = Field(default=5, ge=1, le=100)
    RETRY_BASE_SECONDS: int = Field(default=300, ge=1)
    RETRY_MAX_SECONDS: int = Field(default=86400, ge=1)
    DIARIZATION_CONNECT_TIMEOUT: float = Field(default=10, gt=0)
    DIARIZATION_READ_TIMEOUT: float = Field(default=300, gt=0)
    WORKER_HEARTBEAT_MAX_AGE: int = Field(default=60, ge=10)

    # --- Text Embeddings Inference (TEI) - Portainer ---
    TEI_API_URL: str = "http://localhost:8080"
    TEI_TIMEOUT_SECONDS: float = Field(default=30.0, gt=0)
    EMBEDDING_BATCH_SIZE: int = Field(default=32, ge=1, le=256)
    EMBEDDING_DIMENSION: int = Field(default=768, ge=64, le=4096)

    # --- Chunking Parameters ---
    CHUNK_TARGET_SECONDS: float = Field(default=45.0, ge=10.0, le=300.0)
    CHUNK_OVERLAP_SECONDS: float = Field(default=10.0, ge=0.0, le=60.0)
    CHUNK_MAX_TOKENS_ESTIMATE: int = Field(default=300, ge=50, le=1000)

    # --- Voice Recognition & Speaker Identification (pgvector) ---
    VOICE_EMBEDDING_DIMENSION: int = Field(default=256, ge=64, le=2048)
    VOICE_SIMILARITY_THRESHOLD: float = Field(default=0.65, ge=0.0, le=1.0)
    VOICE_TRAINING_PATH: str = "D:/voice_training"

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
