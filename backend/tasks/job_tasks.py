"""
tasks/job_tasks.py — Celery Task Definitions
=============================================
These are the actual tasks that run the job search agents.

MENTOR NOTE:
  Tasks are simple wrappers — all logic lives in the agent classes.
  This file just:
  1. Fetches the right data from DB
  2. Instantiates the right agent
  3. Runs it
  4. Saves results back to DB
"""

import asyncio
import uuid
from datetime import datetime, timezone

from celery import Task
from loguru import logger
from sqlalchemy import select

from backend.tasks.celery_app import celery_app
from backend.config import settings


# ─── Helper: Run async code in Celery (which is sync) ─────────────────────────
def run_async(coro):
    """Run an async coroutine from sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ─── Task: Run agents for ALL active users ────────────────────────────────────
@celery_app.task(name="backend.tasks.job_tasks.run_all_users", bind=True)
def run_all_users(self):
    """
    Master task: dispatches individual job search tasks
    for every active user with preferences set.
    Called every 4 hours by Celery Beat.
    """
    logger.info("🚀 Starting job agent run for all users...")

    async def _fetch_and_dispatch():
        from backend.database import AsyncSessionFactory
        from backend.models.user import User
        from backend.models.job_preference import JobPreference

        async with AsyncSessionFactory() as db:
            # Get all active job_seeker users who have preferences
            result = await db.execute(
                select(User, JobPreference)
                .join(JobPreference, User.id == JobPreference.user_id)
                .where(User.is_active == True)
                .where(User.role == "job_seeker")
                .where(JobPreference.is_active == True)
            )
            rows = result.all()

        logger.info(f"Found {len(rows)} active users to process.")

        for user, pref in rows:
            for portal in pref.portals:
                # Dispatch individual task per user per portal
                run_job_agent.apply_async(
                    args=[str(user.id), portal],
                    queue="job_search",
                )
                logger.info(f"📋 Queued: user={user.email} portal={portal}")

    run_async(_fetch_and_dispatch())


# ─── Task: Run agent for ONE user on ONE portal ───────────────────────────────
@celery_app.task(
    name="backend.tasks.job_tasks.run_job_agent",
    bind=True,
    max_retries=3,
    default_retry_delay=120,  # 2 minute retry delay
)
def run_job_agent(self, user_id: str, portal: str):
    """
    Runs the full job search + apply cycle for one user on one portal.

    Steps:
    1. Load user credentials and preferences
    2. Launch browser agent for the portal
    3. Login → Search jobs → Score → Apply
    4. Save results to DB
    """
    logger.info(f"🤖 Starting agent: user={user_id} portal={portal}")

    async def _run():
        from backend.database import AsyncSessionFactory
        from backend.models.credential import Credential
        from backend.models.resume import Resume
        from backend.models.job_preference import JobPreference
        from backend.services.credential_manager import credential_manager

        async with AsyncSessionFactory() as db:
            user_uuid = uuid.UUID(user_id)

            # Load credentials
            cred_result = await db.execute(
                select(Credential).where(
                    Credential.user_id == user_uuid,
                    Credential.portal == portal,
                )
            )
            credential = cred_result.scalar_one_or_none()
            if not credential:
                logger.error(f"❌ No {portal} credentials for user {user_id}")
                return

            # Load active resume
            resume_result = await db.execute(
                select(Resume).where(
                    Resume.user_id == user_uuid,
                    Resume.is_active == True,
                    Resume.is_parsed == True,
                )
            )
            resume = resume_result.scalar_one_or_none()
            if not resume:
                logger.warning(f"⚠️ No active parsed resume for user {user_id}")
                return

            # Load preferences
            pref_result = await db.execute(
                select(JobPreference).where(JobPreference.user_id == user_uuid)
            )
            preferences = pref_result.scalar_one_or_none()
            if not preferences:
                logger.error(f"❌ No preferences for user {user_id}")
                return

            # Decrypt credentials (only in memory, never logged)
            username = credential_manager.decrypt(credential.enc_username)
            password = credential_manager.decrypt(credential.enc_password)

        # ── Launch the appropriate agent ───────────────────────────────────
        # (Phase 2 will implement these agents)
        agent = _get_agent(portal)
        if not agent:
            logger.error(f"❌ No agent implemented for portal: {portal}")
            return

        try:
            await agent.launch()
            await agent.login(username, password)
            jobs = await agent.search_jobs(
                keywords=preferences.keywords,
                location=preferences.location,
            )
            logger.info(f"Found {len(jobs)} jobs for user {user_id} on {portal}")

            applied_count = 0
            for job in jobs:
                if applied_count >= preferences.max_apps_per_day:
                    logger.info(f"Daily limit reached for user {user_id}")
                    break
                success = await agent.apply_job(job, resume.parsed_json)
                if success:
                    applied_count += 1

            logger.success(
                f"✅ Done: user={user_id} portal={portal} applied={applied_count}"
            )
        except Exception as e:
            logger.error(f"💥 Agent error: user={user_id} portal={portal} error={e}")
            raise self.retry(exc=e)
        finally:
            await agent.close()

    run_async(_run())


def _get_agent(portal: str):
    """Factory: returns the right agent for a portal. (Phase 2)"""
    # Agents will be implemented in Phase 2
    # from backend.agents.indeed_agent import IndeedAgent
    # from backend.agents.linkedin_agent import LinkedInAgent
    # from backend.agents.dice_agent import DiceAgent
    agents = {
        # "indeed": IndeedAgent,
        # "linkedin": LinkedInAgent,
        # "dice": DiceAgent,
    }
    agent_class = agents.get(portal)
    return agent_class() if agent_class else None


# ─── Task: Parse Resume with AI ───────────────────────────────────────────────
@celery_app.task(name="backend.tasks.job_tasks.parse_resume_task")
def parse_resume_task(resume_id: str):
    """
    Triggered after resume upload.
    Uses GPT-4o to extract structured data from the resume file.
    """
    logger.info(f"📄 Parsing resume: {resume_id}")

    async def _parse():
        from backend.database import AsyncSessionFactory
        from backend.models.resume import Resume
        from backend.services.resume_parser import ResumeParser

        async with AsyncSessionFactory() as db:
            result = await db.execute(
                select(Resume).where(Resume.id == uuid.UUID(resume_id))
            )
            resume = result.scalar_one_or_none()
            if not resume:
                logger.error(f"Resume {resume_id} not found.")
                return

            parser = ResumeParser()
            raw_text, parsed_json = await parser.parse(resume.file_path, resume.file_type)

            resume.raw_text = raw_text
            resume.parsed_json = parsed_json
            resume.is_parsed = True
            await db.commit()

            logger.success(f"✅ Resume {resume_id} parsed successfully.")

    run_async(_parse())


# ─── Task: Daily Report ───────────────────────────────────────────────────────
@celery_app.task(name="backend.tasks.job_tasks.generate_daily_report")
def generate_daily_report():
    """Generates a daily summary of applications. Runs at midnight UTC."""
    logger.info("📊 Generating daily application report...")
    # TODO: Generate and optionally email the report
    # For now, just log the stats
    async def _report():
        from backend.database import AsyncSessionFactory
        from backend.models.application import Application
        from sqlalchemy import func
        from datetime import timedelta

        async with AsyncSessionFactory() as db:
            today = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            result = await db.execute(
                select(
                    Application.status,
                    func.count(Application.id)
                )
                .where(Application.applied_at >= today)
                .group_by(Application.status)
            )
            stats = {row[0]: row[1] for row in result.all()}
            logger.info(f"📊 Daily Report: {stats}")

    run_async(_report())
