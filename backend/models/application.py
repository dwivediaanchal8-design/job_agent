"""
models/application.py — Job Applications Table
================================================
Tracks every job application submitted by the agent.
This is the history log — one row per application attempt.

Columns:
    id              UUID primary key
    user_id         FK → users.id
    portal          Which portal was used
    job_title       Job title from listing
    company         Company name
    job_url         Direct URL to the job listing
    job_description Raw job description text
    match_score     AI relevance score (0-100)
    status          'applied' | 'failed' | 'skipped' | 'pending'
    failure_reason  Why it failed (CAPTCHA, form error, etc.)
    applied_at      When application was submitted
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Boolean, DateTime, ForeignKey, Integer, Text, Float, func, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Application(Base):
    __tablename__ = "applications"

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
    )

    # ─── Job Info ─────────────────────────────────────────────────────────────
    portal: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    job_title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    job_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    job_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ─── AI Scoring ───────────────────────────────────────────────────────────
    match_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ─── Application Status ───────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        SAEnum(
            "pending",    # Queued, not yet processed
            "applied",    # Successfully submitted
            "failed",     # Error during submission
            "skipped",    # Score too low or already applied
            name="application_status",
        ),
        nullable=False,
        default="pending",
        index=True,
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ─── Timestamps ───────────────────────────────────────────────────────────
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    # ─── Relationships ────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship(back_populates="applications")

    def __repr__(self) -> str:
        return (
            f"<Application user={self.user_id} "
            f"job='{self.job_title}' @ {self.company} "
            f"status={self.status}>"
        )
