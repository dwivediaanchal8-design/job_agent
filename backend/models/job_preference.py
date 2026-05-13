"""
models/job_preference.py — Job Preferences Table
==================================================
Stores each user's job search criteria.
The agent uses these to search and filter jobs on portals.

Columns:
    id              UUID primary key
    user_id         FK → users.id
    keywords        Job title keywords e.g. ["Python Developer", "Backend Engineer"]
    location        Target location e.g. "New York, NY" or "Remote"
    job_type        'full_time' | 'part_time' | 'contract' | 'remote'
    salary_min      Minimum salary filter (USD)
    portals         Which portals to use e.g. ["linkedin", "indeed", "dice"]
    max_apps_per_day Override global rate limit per user
    is_active       Whether this preference set is active
    updated_at      Timestamp
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Boolean, DateTime, ForeignKey, Integer, Enum as SAEnum, func, Uuid, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class JobPreference(Base):
    __tablename__ = "job_preferences"

    # ─── Primary Key ──────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )

    # ─── Foreign Key ──────────────────────────────────────────────────────────
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,  # One preference set per user (update, don't duplicate)
    )

    # ─── Search Criteria ──────────────────────────────────────────────────────
    # PostgreSQL ARRAY for multiple keywords
    keywords: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    location: Mapped[str] = mapped_column(String(255), nullable=False, default="Remote")
    job_type: Mapped[str] = mapped_column(
        SAEnum("full_time", "part_time", "contract", "remote", name="job_type"),
        nullable=False,
        default="full_time",
    )

    # ─── Salary Filter ────────────────────────────────────────────────────────
    salary_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # ─── Portal Selection ─────────────────────────────────────────────────────
    # Which portals to run the agent on for this user
    portals: Mapped[list] = mapped_column(
        JSON, nullable=False, default=lambda: ["indeed"]
    )

    # ─── Rate Limiting ────────────────────────────────────────────────────────
    max_apps_per_day: Mapped[int] = mapped_column(Integer, default=50)

    # ─── Status ───────────────────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # ─── Timestamp ────────────────────────────────────────────────────────────
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ─── Relationships ────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship(back_populates="preferences")

    def __repr__(self) -> str:
        return f"<JobPreference user={self.user_id} keywords={self.keywords}>"
