"""
schemas/user.py — User Request & Response Schemas
===================================================
Pydantic v2 models for API validation.

MENTOR NOTE:
  Schemas ≠ DB Models.
  - DB Models (SQLAlchemy) define how data is STORED.
  - Schemas (Pydantic) define what the API ACCEPTS and RETURNS.
  - Never expose hashed_password in responses — use UserResponse.
"""

import uuid
from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


# ─── Auth Schemas ─────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    """Used to register a new admin account."""
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=100)
    role: Literal["admin", "job_seeker"] = "job_seeker"


class LoginRequest(BaseModel):
    """Used for admin login."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Returned after successful login."""
    access_token: str
    token_type: str = "bearer"
    user_id: uuid.UUID
    role: str


# ─── User Schemas ─────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    """Add a new job-seeker user to the system."""
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=100)
    role: Literal["admin", "job_seeker"] = "job_seeker"


class UserUpdate(BaseModel):
    """Update user info."""
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    """Safe user response — NEVER includes hashed_password."""
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}  # Pydantic v2 ORM mode


class UserListResponse(BaseModel):
    """Paginated user list."""
    users: list[UserResponse]
    total: int
