"""
api/credentials.py — Portal Credential Management
===================================================
Endpoints:
    POST   /credentials         → Save encrypted portal credentials
    GET    /credentials/{user}  → List user's credentials (metadata only)
    DELETE /credentials/{id}    → Remove credentials
    POST   /preferences         → Set job preferences
    GET    /preferences/{user}  → Get user's preferences
    PATCH  /preferences/{user}  → Update preferences
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from backend.database import get_db
from backend.models.credential import Credential
from backend.models.job_preference import JobPreference
from backend.auth import get_current_user_id, require_admin
from backend.services.credential_manager import credential_manager
from backend.schemas.credential import (
    CredentialCreate, CredentialResponse,
    PreferenceCreate, PreferenceResponse,
)

router = APIRouter(tags=["Credentials & Preferences"])


# ─── Credentials ──────────────────────────────────────────────────────────────

@router.post("/credentials", response_model=CredentialResponse, status_code=201)
async def save_credential(
    payload: CredentialCreate,
    admin_id: uuid.UUID = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Save portal credentials for a user.
    Passwords are encrypted BEFORE saving to database.
    Admin only.
    """
    # Check if credential already exists for this user+portal
    result = await db.execute(
        select(Credential).where(
            Credential.user_id == payload.user_id,
            Credential.portal == payload.portal,
        )
    )
    existing = result.scalar_one_or_none()

    # Encrypt both username and password
    enc_username = credential_manager.encrypt(payload.username)
    enc_password = credential_manager.encrypt(payload.password)

    if existing:
        # Update existing credential
        existing.enc_username = enc_username
        existing.enc_password = enc_password
        existing.is_verified = False  # Reset — needs re-verification
        credential = existing
        logger.info(f"🔄 Updated {payload.portal} credentials for user {payload.user_id}")
    else:
        # Create new credential
        credential = Credential(
            user_id=payload.user_id,
            portal=payload.portal,
            enc_username=enc_username,
            enc_password=enc_password,
        )
        db.add(credential)
        logger.info(f"🔑 Saved {payload.portal} credentials for user {payload.user_id}")

    await db.flush()
    return credential


@router.get("/credentials/{user_id}", response_model=list[CredentialResponse])
async def get_user_credentials(
    user_id: uuid.UUID,
    admin_id: uuid.UUID = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get all credential metadata for a user. NEVER returns actual passwords."""
    result = await db.execute(
        select(Credential).where(Credential.user_id == user_id)
    )
    return result.scalars().all()


@router.delete("/credentials/{credential_id}", status_code=204)
async def delete_credential(
    credential_id: uuid.UUID,
    admin_id: uuid.UUID = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a portal credential."""
    result = await db.execute(select(Credential).where(Credential.id == credential_id))
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found.")
    await db.delete(cred)
    logger.info(f"🗑️ Deleted credential {credential_id}")


# ─── Job Preferences ──────────────────────────────────────────────────────────

@router.post("/preferences", response_model=PreferenceResponse, status_code=201)
async def save_preferences(
    payload: PreferenceCreate,
    admin_id: uuid.UUID = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Set job search preferences for a user."""
    result = await db.execute(
        select(JobPreference).where(JobPreference.user_id == payload.user_id)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.keywords = payload.keywords
        existing.location = payload.location
        existing.job_type = payload.job_type
        existing.salary_min = payload.salary_min
        existing.portals = payload.portals
        existing.max_apps_per_day = payload.max_apps_per_day
        pref = existing
        logger.info(f"🔄 Updated preferences for user {payload.user_id}")
    else:
        pref = JobPreference(**payload.model_dump())
        db.add(pref)
        logger.info(f"⚙️ Created preferences for user {payload.user_id}")

    await db.flush()
    return pref


@router.get("/preferences/{user_id}", response_model=PreferenceResponse)
async def get_preferences(
    user_id: uuid.UUID,
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get job preferences for a user."""
    result = await db.execute(
        select(JobPreference).where(JobPreference.user_id == user_id)
    )
    pref = result.scalar_one_or_none()
    if not pref:
        raise HTTPException(status_code=404, detail="No preferences set for this user.")
    return pref
