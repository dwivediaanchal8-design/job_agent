"""
api/logs.py — System Logs Endpoint
===================================
Provides real-time access to the agent.log file for the dashboard.
"""

import os
from fastapi import APIRouter, Depends, Query
from backend.auth import require_admin
from backend.config import settings
import uuid

router = APIRouter(prefix="/logs", tags=["System"])

@router.get("")
async def get_logs(
    lines: int = Query(default=100, ge=10, le=500),
    admin_id: uuid.UUID = Depends(require_admin),
):
    """
    Returns the last N lines of the log file.
    """
    log_path = settings.log_file
    
    if not os.path.exists(log_path):
        return {"logs": ["Log file not found."]}

    try:
        with open(log_path, "r") as f:
            # Simple tail implementation
            content = f.readlines()
            last_lines = content[-lines:]
            return {"logs": [line.strip() for line in last_lines]}
    except Exception as e:
        return {"error": f"Failed to read logs: {str(e)}"}
