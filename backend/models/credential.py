"""
models/credential.py — Portal Credentials Table
=================================================
Stores encrypted login credentials for each job portal.
Passwords are NEVER stored in plain text — always Fernet encrypted.

Columns:
    id              UUID primary key
    user_id         FK → users.id
    portal          'linkedin' | 'indeed' | 'dice'
    enc_username    Fernet-encrypted username/email
    enc_password    Fernet-encrypted password
    cookies_path    Path to saved browser cookies (skip re-login)
    is_verified     Whether login was last successful
    last_login_at   Last successful login timestamp
    updated_at      Timestamp
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Boolean, DateTime, ForeignKey, Enum as SAEnum, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from backend.database import Base


class Credential(Base):
    __tablename__ = "credentials"

    # ─── Primary Key ──────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ─── Foreign Key ──────────────────────────────────────────────────────────
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ─── Portal ───────────────────────────────────────────────────────────────
    portal: Mapped[str] = mapped_column(
        SAEnum("linkedin", "indeed", "dice", name="portal_name"),
        nullable=False,
    )

    # ─── Encrypted Credentials ────────────────────────────────────────────────
    # These are stored as Fernet-encrypted base64 strings
    # Only the MASTER_ENCRYPTION_KEY (in .env) can decrypt them
    enc_username: Mapped[str] = mapped_column(Text, nullable=False)
    enc_password: Mapped[str] = mapped_column(Text, nullable=False)

    # ─── Session Management ───────────────────────────────────────────────────
    # Path to saved cookies file — avoids re-login on every run
    cookies_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ─── Timestamps ───────────────────────────────────────────────────────────
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ─── Relationships ────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship(back_populates="credentials")

    def __repr__(self) -> str:
        return f"<Credential user={self.user_id} portal={self.portal}>"
