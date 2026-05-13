
import os
import sys
import time
import redis
import uuid
from loguru import logger
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.tasks.celery_app import celery_app
from backend.tasks.job_tasks import run_job_agent
from backend.config import settings
from unittest.mock import MagicMock

def test_phase4(demo=False):
    print("==================================================")
    print("  PHASE 4 VERIFICATION — SCHEDULER & CELERY")
    print("  " + ("(SIMULATED DEMO MODE)" if demo else "(LIVE MODE)"))
    print("==================================================")

    # 1. Check Redis
    print("\n[1/4] Checking Redis connectivity...")
    try:
        if demo:
            print("... [DEMO] Mocking Redis ping...")
            time.sleep(1)
            print("[OK] Redis is online! (Mocked)")
        else:
            r = redis.from_url(settings.redis_url)
            r.ping()
            print("[OK] Redis is online!")
    except Exception as e:
        print(f"[FAIL] Redis is OFFLINE at {settings.redis_url}")
        print("   FIX: Run 'docker-compose up -d' to start Redis.")
        return

    # 2. Check Celery App
    print("\n[2/4] Checking Celery application...")
    if celery_app:
        print(f"[OK] Celery app initialized: {celery_app.main}")
    else:
        print("[FAIL] Celery app failed to initialize.")
        return

    # 3. Check Task Discovery
    print("\n[3/4] Checking task registration...")
    registered_tasks = celery_app.tasks.keys()
    required_tasks = [
        "backend.tasks.job_tasks.run_job_agent",
        "backend.tasks.job_tasks.run_all_users",
        "backend.tasks.job_tasks.generate_daily_report"
    ]
    
    all_found = True
    for task in required_tasks:
        if task in registered_tasks:
            print(f"[OK] Found task: {task}")
        else:
            print(f"[FAIL] Missing task: {task}")
            all_found = False
    
    if not all_found:
        print("   FIX: Ensure tasks are imported in backend/tasks/celery_app.py")
        return

    # 4. Instructions for Live Test
    print("\n[4/4] Instructions for Live Execution Test:")
    print("--------------------------------------------------")
    print("To verify the worker actually processes tasks:")
    print("1. Start the worker in a NEW terminal:")
    print("   venv\\Scripts\\celery -A backend.tasks.celery_app worker --loglevel=info -P solo")
    print("\n2. Trigger a dry-run task (replace USER_ID with a real one from DB):")
    print("   python -c \"from backend.tasks.job_tasks import run_job_agent; run_job_agent.delay('USER_ID', 'indeed', dry_run=True)\"")
    print("\n3. Check logs/agent.log for execution details.")
    print("--------------------------------------------------")

if __name__ == "__main__":
    load_dotenv()
    is_demo = "--demo" in sys.argv
    test_phase4(demo=is_demo)
