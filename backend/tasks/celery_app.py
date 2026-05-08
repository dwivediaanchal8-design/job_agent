"""
tasks/celery_app.py — Celery Configuration
============================================
Sets up Celery with Redis broker.
Also configures Celery Beat for scheduled runs.

MENTOR NOTE:
  Three processes need to run simultaneously:
  1. uvicorn  → Serves the API
  2. celery worker → Processes tasks
  3. celery beat   → Triggers scheduled tasks

  Start all three when running the system.
"""

from celery import Celery
from celery.schedules import crontab
from kombu import Queue

from backend.config import settings

# ─── Create Celery App ────────────────────────────────────────────────────────
celery_app = Celery(
    "job_agent",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["backend.tasks.job_tasks"],  # Register task modules
)

# ─── Celery Configuration ─────────────────────────────────────────────────────
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task settings
    task_track_started=True,
    task_acks_late=True,           # Acknowledge AFTER completion (safer)
    task_reject_on_worker_lost=True,

    # Result expiry: keep results for 24 hours
    result_expires=86400,

    # Retry settings
    task_max_retries=3,
    task_default_retry_delay=60,   # 60 seconds between retries

    # Concurrency: how many users run in parallel
    worker_concurrency=4,

    # Queues
    task_default_queue="default",
    task_queues=(
        Queue("default"),
        Queue("job_search"),       # High priority job searching
        Queue("reporting"),        # Low priority daily reports
    ),
)

# ─── Scheduled Tasks (Celery Beat) ────────────────────────────────────────────
celery_app.conf.beat_schedule = {
    # Run job search for ALL active users every 4 hours
    "run-job-agents-every-4h": {
        "task": "backend.tasks.job_tasks.run_all_users",
        "schedule": crontab(minute=0, hour="*/4"),
        "options": {"queue": "job_search"},
    },

    # Generate daily report at midnight UTC
    "daily-report-midnight": {
        "task": "backend.tasks.job_tasks.generate_daily_report",
        "schedule": crontab(minute=0, hour=0),
        "options": {"queue": "reporting"},
    },
}
