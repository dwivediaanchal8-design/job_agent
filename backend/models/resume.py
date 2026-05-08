"""
models/resume.py — Resume Table
================================
Stores uploaded resume files and their AI-parsed structured data.

Columns:
    id              UUID primary key
    user_id         FK → users.id
    file_name       Original filename
    file_path       Server storage path
    file_type       'pdf' or 'docx'
    raw_text        Extracted plain text from file
    parsed_json     GPT-4o structured extraction (skills, experience, etc.)
    is_active       Only the active resume is used for applications
    created_at      Upload timestamp
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from backend.database import Base


class Resume(Base):
    __tablename__ = "resumes"

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

    # ─── File Info ────────────────────────────────────────────────────────────
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(
        String(10), nullable=False  # 'pdf' or 'docx'
    )

    # ─── Content ──────────────────────────────────────────────────────────────
    # raw_text: full text extracted from PDF/DOCX
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # parsed_json: GPT-4o structured extraction stored as JSONB
    # Structure: {"name": "...", "skills": [...], "experience": [...], ...}
    parsed_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # ─── Status ───────────────────────────────────────────────────────────────
    # Only one resume should be active per user
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_parsed: Mapped[bool] = mapped_column(Boolean, default=False)

    # ─── Timestamp ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ─── Relationships ────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship(back_populates="resumes")

    def __repr__(self) -> str:
        return f"<Resume user={self.user_id} file={self.file_name} parsed={self.is_parsed}>"
