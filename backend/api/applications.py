"""
api/applications.py — Application History & Stats
===================================================
Endpoints:
    GET /applications              → All applications (filtered)
    GET /applications/stats        → Dashboard stats
    GET /applications/user/{id}    → Applications for specific user
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from backend.database import get_db
from backend.models.application import Application
from backend.auth import require_admin
from backend.schemas.application import (
    ApplicationListResponse, ApplicationStats, ApplicationResponse
)

router = APIRouter(prefix="/applications", tags=["Applications"])


@router.get("/stats", response_model=ApplicationStats)
async def get_stats(
    admin_id: uuid.UUID = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get dashboard overview stats — applications today and all time."""
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # Today's counts by status
    today_total = await db.execute(
        select(func.count(Application.id))
        .where(Application.applied_at >= today_start)
    )
    today_applied = await db.execute(
        select(func.count(Application.id)).where(
            and_(Application.applied_at >= today_start, Application.status == "applied")
        )
    )
    today_failed = await db.execute(
        select(func.count(Application.id)).where(
            and_(Application.applied_at >= today_start, Application.status == "failed")
        )
    )
    all_time = await db.execute(select(func.count(Application.id)))

    # Breakdown by portal
    portal_rows = await db.execute(
        select(Application.portal, func.count(Application.id))
        .group_by(Application.portal)
    )
    portals = {row[0]: row[1] for row in portal_rows.all()}

    return ApplicationStats(
        total_today=today_total.scalar() or 0,
        applied_today=today_applied.scalar() or 0,
        failed_today=today_failed.scalar() or 0,
        total_all_time=all_time.scalar() or 0,
        portals_breakdown=portals,
    )


@router.get("", response_model=ApplicationListResponse)
async def list_applications(
    user_id: Optional[uuid.UUID] = Query(default=None),
    portal: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    admin_id: uuid.UUID = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    List applications with optional filters.
    Supports filtering by user, portal, and status.
    """
    query = select(Application).order_by(Application.applied_at.desc())

    if user_id:
        query = query.where(Application.user_id == user_id)
    if portal:
        query = query.where(Application.portal == portal)
    if status:
        query = query.where(Application.status == status)

    result = await db.execute(query.offset(skip).limit(limit))
    apps = result.scalars().all()

    # Count totals for each status
    total = await db.execute(select(func.count(Application.id)))
    applied = await db.execute(
        select(func.count(Application.id)).where(Application.status == "applied")
    )
    failed = await db.execute(
        select(func.count(Application.id)).where(Application.status == "failed")
    )
    skipped = await db.execute(
        select(func.count(Application.id)).where(Application.status == "skipped")
    )

    return ApplicationListResponse(
        applications=apps,
        total=total.scalar() or 0,
        applied_count=applied.scalar() or 0,
        failed_count=failed.scalar() or 0,
        skipped_count=skipped.scalar() or 0,
    )


@router.get("/user/{user_id}", response_model=list[ApplicationResponse])
async def get_user_applications(
    user_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    admin_id: uuid.UUID = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get recent applications for a specific user."""
    result = await db.execute(
        select(Application)
        .where(Application.user_id == user_id)
        .order_by(Application.applied_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.post("/reset/{user_id}", status_code=200)
async def reset_daily_applications(
    user_id: uuid.UUID,
    admin_id: uuid.UUID = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Reset a user's daily application count.
    Deletes all application records from today for this user.
    Admin only.
    """
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    
    from sqlalchemy import delete
    result = await db.execute(
        delete(Application).where(
            and_(Application.user_id == user_id, Application.applied_at >= today_start)
        )
    )
    
    logger.warning(f"🔄 Admin {admin_id} reset daily applications for user {user_id}")
    return {"message": "Daily application count reset successfully.", "deleted_count": result.rowcount}
