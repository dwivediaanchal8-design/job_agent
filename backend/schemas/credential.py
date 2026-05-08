"""
schemas/credential.py — Credential Request & Response Schemas
==============================================================
"""

import uuid
from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, Field


class CredentialCreate(BaseModel):
    """Save portal login credentials for a user."""
    user_id: uuid.UUID
    portal: Literal["linkedin", "indeed", "dice"]
    username: str = Field(min_length=1, max_length=255)  # email or username
    password: str = Field(min_length=1, max_length=255)  # plain — encrypted before storing


class CredentialUpdate(BaseModel):
    """Update existing credential."""
    username: Optional[str] = Field(default=None, max_length=255)
    password: Optional[str] = Field(default=None, max_length=255)


class CredentialResponse(BaseModel):
    """
    Credential info returned by API.
    NEVER includes the actual username/password — only metadata.
    """
    id: uuid.UUID
    user_id: uuid.UUID
    portal: str
    is_verified: bool
    last_login_at: Optional[datetime]
    updated_at: datetime

    model_config = {"from_attributes": True}


class PreferenceCreate(BaseModel):
    """Set job search preferences for a user."""
    user_id: uuid.UUID
    keywords: list[str] = Field(min_length=1)
    location: str = Field(default="Remote", max_length=255)
    job_type: Literal["full_time", "part_time", "contract", "remote"] = "full_time"
    salary_min: Optional[int] = Field(default=None, ge=0)
    portals: list[Literal["linkedin", "indeed", "dice"]] = ["indeed"]
    max_apps_per_day: int = Field(default=50, ge=1, le=200)


class PreferenceResponse(BaseModel):
    """Job preference response."""
    id: uuid.UUID
    user_id: uuid.UUID
    keywords: list[str]
    location: str
    job_type: str
    salary_min: Optional[int]
    portals: list[str]
    max_apps_per_day: int
    is_active: bool
    updated_at: datetime

    model_config = {"from_attributes": True}
