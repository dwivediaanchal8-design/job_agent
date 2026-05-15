import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path
root = Path(__file__).resolve().parent.parent
sys.path.append(str(root))

from loguru import logger
from backend.tasks.job_tasks import run_job_agent

# Configuration
USER_EMAIL = "dwivediaanchal8@gmail.com"
PORTAL = "dice" # Change to "indeed" if desired
DRY_RUN = True

def test_run():
    logger.info(f"🧪 Starting verification run for {USER_EMAIL} on {PORTAL}...")
    
    # We need to get the user_id first
    from backend.database import SyncSessionFactory
    from backend.models.user import User
    from sqlalchemy import select
    
    with SyncSessionFactory() as db:
        user = db.execute(select(User).where(User.email == USER_EMAIL)).scalar_one_or_none()
        if not user:
            logger.error(f"User {USER_EMAIL} not found. Please run scripts/onboard_user.py first.")
            return
        user_id = str(user.id)
    
    logger.info(f"Found user ID: {user_id}")
    
    # Run the agent task (dry_run=True means it won't actually click submit)
    # Note: run_job_agent is a Celery task, but we can call it directly for testing.
    try:
        # We call the function directly (bypass Celery queue for this test)
        # This will use the actual browser-based agent logic.
        summary = run_job_agent(user_id, PORTAL, dry_run=DRY_RUN)
        
        logger.success("🏁 Verification run complete!")
        logger.info(f"Summary: {summary}")
        
        if summary.get("applied", 0) > 0 or summary.get("total_found", 0) > 0:
            logger.success("✨ Pipeline is functional! Agent found/processed jobs.")
        else:
            logger.warning("⚠️ No jobs found or processed. Check keywords/location or portal status.")
            
    except Exception as e:
        logger.error(f"❌ Verification run failed: {e}")

if __name__ == "__main__":
    test_run()
