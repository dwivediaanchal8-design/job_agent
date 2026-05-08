"""
api/resumes.py — Resume Upload & Management
=============================================
Endpoints:
    POST /resumes/upload/{user_id}   → Upload PDF or DOCX
    GET  /resumes/{user_id}          → List user's resumes
    POST /resumes/{resume_id}/parse  → Trigger AI parsing manually
    PATCH /resumes/{resume_id}/activate → Set as active resume
"""

import uuid
import os
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from loguru import logger

from backend.database import get_db
from backend.models.resume import Resume
from backend.auth import require_admin
from backend.config import settings
from backend.schemas.application import ResumeResponse

router = APIRouter(prefix="/resumes", tags=["Resumes"])

ALLOWED_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}
MAX_SIZE_BYTES = settings.max_file_size_mb * 1024 * 1024


@router.post("/upload/{user_id}", response_model=ResumeResponse, status_code=201)
async def upload_resume(
    user_id: uuid.UUID,
    file: UploadFile = File(...),
    admin_id: uuid.UUID = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a resume for a user.
    Accepts PDF or DOCX only. Max 10MB.
    AI parsing is triggered automatically after upload.
    """
    # ── Validate file type ─────────────────────────────────────────────────
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only PDF and DOCX files allowed. Got: {file.content_type}",
        )

    # ── Validate file size ─────────────────────────────────────────────────
    content = await file.read()
    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max size: {settings.max_file_size_mb}MB",
        )

    # ── Save file to disk ──────────────────────────────────────────────────
    upload_dir = Path(settings.upload_dir) / str(user_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_ext = ALLOWED_TYPES[file.content_type]
    safe_filename = f"{uuid.uuid4()}.{file_ext}"
    file_path = upload_dir / safe_filename

    with open(file_path, "wb") as f:
        f.write(content)

    logger.info(f"📄 Resume uploaded for user {user_id}: {safe_filename}")

    # ── Deactivate other resumes for this user ─────────────────────────────
    await db.execute(
        update(Resume)
        .where(Resume.user_id == user_id)
        .values(is_active=False)
    )

    # ── Create DB record ───────────────────────────────────────────────────
    resume = Resume(
        user_id=user_id,
        file_name=file.filename or safe_filename,
        file_path=str(file_path),
        file_type=file_ext,
        is_active=True,
        is_parsed=False,
    )
    db.add(resume)
    await db.flush()

    # ── Trigger async AI parsing ───────────────────────────────────────────
    # This runs in background — doesn't block the response
    try:
        from backend.tasks.job_tasks import parse_resume_task
        parse_resume_task.delay(str(resume.id))
        logger.info(f"🤖 Resume parsing queued for resume {resume.id}")
    except Exception as e:
        logger.warning(f"Could not queue parsing task (Celery may not be running): {e}")

    return resume


@router.get("/{user_id}", response_model=list[ResumeResponse])
async def list_resumes(
    user_id: uuid.UUID,
    admin_id: uuid.UUID = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all resumes for a user."""
    result = await db.execute(
        select(Resume)
        .where(Resume.user_id == user_id)
        .order_by(Resume.created_at.desc())
    )
    return result.scalars().all()


@router.patch("/{resume_id}/activate", response_model=ResumeResponse)
async def activate_resume(
    resume_id: uuid.UUID,
    admin_id: uuid.UUID = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Set a specific resume as the active one for a user."""
    result = await db.execute(select(Resume).where(Resume.id == resume_id))
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found.")

    # Deactivate all others
    await db.execute(
        update(Resume)
        .where(Resume.user_id == resume.user_id)
        .values(is_active=False)
    )
    resume.is_active = True
    logger.info(f"✅ Resume {resume_id} set as active for user {resume.user_id}")
    return resume
