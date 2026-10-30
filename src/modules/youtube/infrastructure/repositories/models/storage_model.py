"""Durable settings, remote inventory, transfers and append-only storage history."""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database.connector import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StorageSettingsModel(Base):
    __tablename__ = "youtube_storage_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mode: Mapped[str] = mapped_column(String(10), default="BOTH")
    uploads_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    max_upload_mib_per_second: Mapped[float | None] = mapped_column(Float)
    drive_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    drive_info: Mapped[dict] = mapped_column(JSON, default=dict)
    last_error: Mapped[str | None] = mapped_column(Text)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    catalog_error: Mapped[str | None] = mapped_column(Text)
    catalog_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DriveOAuthSessionModel(Base):
    __tablename__ = "youtube_drive_oauth_sessions"

    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    code_verifier: Mapped[str] = mapped_column(Text)
    redirect_uri: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DriveBackupModel(Base):
    __tablename__ = "youtube_drive_backups"

    content_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String, unique=True)
    title: Mapped[str] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    relative_path: Mapped[str] = mapped_column(Text)
    file_id: Mapped[str | None] = mapped_column(String, unique=True)
    web_url: Mapped[str | None] = mapped_column(Text)
    size: Mapped[int] = mapped_column(BigInteger, default=0)
    md5: Mapped[str | None] = mapped_column(String(32))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StorageTransferModel(Base):
    __tablename__ = "youtube_storage_transfers"
    __table_args__ = (
        Index("ix_youtube_storage_transfer_queue", "status", "next_retry_at", "id"),
        Index("uq_youtube_storage_transfer", "content_id", "operation", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content_id: Mapped[int] = mapped_column(Integer)
    operation: Mapped[str] = mapped_column(String(10))
    mode: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    bytes_transferred: Mapped[int] = mapped_column(BigInteger, default=0)
    total_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    session_uri: Mapped[str | None] = mapped_column(Text)
    lease_token: Mapped[str | None] = mapped_column(String)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class StorageEventModel(Base):
    __tablename__ = "youtube_storage_events"
    __table_args__ = (Index("ix_youtube_storage_event_content", "content_id", "id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content_id: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(40))
    previous_location: Mapped[str | None] = mapped_column(String(10))
    new_location: Mapped[str | None] = mapped_column(String(10))
    details: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
