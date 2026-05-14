"""
api/jobs.py — Job Automation Control
======================================
Endpoints to manually trigger and monitor job agent tasks.
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from loguru import logger

from backend.auth import require_admin
from backend.tasks.job_tasks import run_job_agent, run_all_users

router = APIRouter(prefix="/jobs", tags=["Job Automation"])

class JobRunRequest(BaseModel):
    user_id: uuid.UUID
    portal: str  # 'indeed', 'dice', 'linkedin'
    dry_run: bool = True

class JobRunResponse(BaseModel):
    task_id: str
    status: str
    message: str

@router.post("/run", response_model=JobRunResponse)
async def trigger_job_run(
    payload: JobRunRequest,
    admin_id: uuid.UUID = Depends(require_admin),
):
    """
    Manually trigger a job search & apply task for a specific user and portal.
    Returns the Celery task ID.
    """
    logger.info(f"🚀 Manual trigger: user={payload.user_id} portal={payload.portal} dry_run={payload.dry_run}")
    
    try:
        # Dispatch the Celery task
        task = run_job_agent.apply_async(
            args=[str(payload.user_id), payload.portal],
            kwargs={"dry_run": payload.dry_run},
            queue="job_search"
        )
        
        return JobRunResponse(
            task_id=task.id,
            status="dispatched",
            message=f"Job agent task started for {payload.portal}"
        )
    except Exception as e:
        logger.error(f"Failed to dispatch job task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/run-all", status_code=202)
async def trigger_run_all(
    admin_id: uuid.UUID = Depends(require_admin),
):
    """
    Trigger the global 'run all users' task immediately.
    """
    logger.info(f"🚀 Manual trigger: run_all_users by admin {admin_id}")
    task = run_all_users.delay()
    return {"task_id": task.id, "status": "dispatched", "message": "Global job search dispatched for all active users."}

@router.get("/status/{task_id}")
async def get_task_status(
    task_id: str,
    admin_id: uuid.UUID = Depends(require_admin),
):
    """
    Check the status of a specific Celery task.
    """
    from backend.tasks.celery_app import celery_app
    res = celery_app.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": res.status,
        "result": res.result if res.ready() else None
    }
