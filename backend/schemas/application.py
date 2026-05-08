"""
schemas/application.py — Application Request & Response Schemas
================================================================
"""

import uuid
from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, Field


class ApplicationResponse(BaseModel):
    """Single application record returned by API."""
    id: uuid.UUID
    user_id: uuid.UUID
    portal: str
    job_title: str
    company: str
    job_url: str
    match_score: Optional[float]
    status: str
    failure_reason: Optional[str]
    applied_at: datetime

    model_config = {"from_attributes": True}


class ApplicationListResponse(BaseModel):
    """Paginated application list with stats."""
    applications: list[ApplicationResponse]
    total: int
    applied_count: int
    failed_count: int
    skipped_count: int


class ApplicationStats(BaseModel):
    """Dashboard summary stats."""
    total_today: int
    applied_today: int
    failed_today: int
    total_all_time: int
    portals_breakdown: dict[str, int]


class ResumeResponse(BaseModel):
    """Resume info returned by API."""
    id: uuid.UUID
    user_id: uuid.UUID
    file_name: str
    file_type: str
    is_active: bool
    is_parsed: bool
    created_at: datetime

    model_config = {"from_attributes": True}
