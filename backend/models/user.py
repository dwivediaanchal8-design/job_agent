"""
models/user.py — User Table
============================
Represents admin users who manage the system AND
job-seeker users whose applications are automated.

Columns:
    id              UUID primary key
    email           Unique email (used for login)
    full_name       Display name
    hashed_password bcrypt hash — NEVER store plain text
    role            'admin' or 'job_seeker'
    is_active       Can be paused by admin
    created_at      Timestamp
    updated_at      Timestamp
"""

import uuid
from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, Enum as SAEnum, func, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class User(Base):
    __tablename__ = "users"

    # ─── Primary Key ──────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # ─── Identity ─────────────────────────────────────────────────────────────
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # ─── Role: 'admin' manages the system, 'job_seeker' is automated ──────────
    role: Mapped[str] = mapped_column(
        SAEnum("admin", "job_seeker", name="user_role"),
        nullable=False,
        default="job_seeker",
    )

    # ─── Status: Admin can pause a user to stop their job applications ─────────
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ─── Timestamps ───────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ─── Relationships ────────────────────────────────────────────────────────
    credentials: Mapped[list["Credential"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    resumes: Mapped[list["Resume"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    preferences: Mapped[list["JobPreference"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    applications: Mapped[list["Application"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"
