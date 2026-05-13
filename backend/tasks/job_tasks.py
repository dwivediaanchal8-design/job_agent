"""
tasks/job_tasks.py — Celery Task Definitions
=============================================
These are the tasks the Celery worker executes.
Celery Beat (the scheduler) triggers them on a schedule.

MENTOR NOTE on how this all connects:
  1. Celery Beat fires "run-job-agents-every-4h" every 4 hours
  2. That calls run_all_users() → fetches all active users from DB
  3. For each user, dispatches run_job_agent(user_id, portal) as a separate task
  4. Each run_job_agent task:
       a. Gets user credentials + preferences from DB
       b. Decrypts credentials using CredentialManager (Fernet)
       c. Runs the correct agent (Indeed/Dice/LinkedIn)
       d. Saves each ApplicationResult to the applications table
  5. At midnight, generate_daily_report() summarizes today's applications

To test manually (dry_run=True so nothing actually submits):
    # 1. Start a worker:
    celery -A backend.tasks.celery_app worker --loglevel=info -P solo

    # 2. Trigger a task in a separate terminal:
    python -c "
    from backend.tasks.job_tasks import run_job_agent
    result = run_job_agent.apply(args=['YOUR-USER-UUID', 'indeed'], kwargs={'dry_run': True})
    print(result.get())
    "
"""

import asyncio
import uuid
from datetime import date, datetime
from typing import Optional

from loguru import logger
from sqlalchemy import select, func, and_

from backend.tasks.celery_app import celery_app
from backend.services.notifier import notifier


# ─── Helper: Run async code in Celery (which is sync) ────────────────────────

def _run_async(coro):
    """
    Celery workers are synchronous. Our agents are async (Playwright requires it).
    This helper creates a new event loop, runs the async code, then closes it.

    MENTOR NOTE:
      We use asyncio.run() NOT asyncio.get_event_loop() because in a Celery
      worker, there is no existing running loop. asyncio.run() creates a fresh
      loop each time, which is exactly what we need.
    """
    return asyncio.run(coro)


# ─── Helper: Get Sync DB Session ─────────────────────────────────────────────

def _get_sync_session():
    """Returns a sync SQLAlchemy session for use in Celery tasks."""
    from backend.database import SyncSessionFactory
    return SyncSessionFactory()


# ─── DB Helpers ───────────────────────────────────────────────────────────────

def _get_user_data(user_id: str) -> Optional[dict]:
    """
    Fetches all data needed to run the agent for a user.
    Returns None if user not found or not active.
    """
    try:
        from backend.models.user import User
        from backend.models.resume import Resume
        from backend.models.job_preference import JobPreference

        with _get_sync_session() as db:
            user = db.execute(
                select(User).where(
                    User.id == uuid.UUID(user_id),
                    User.is_active == True,
                )
            ).scalar_one_or_none()

            if not user:
                logger.warning(f"[job_tasks] User {user_id} not found or inactive")
                return None

            prefs = db.execute(
                select(JobPreference).where(
                    JobPreference.user_id == user.id,
                    JobPreference.is_active == True,
                )
            ).scalar_one_or_none()

            if not prefs:
                logger.warning(f"[job_tasks] No active preferences for user {user_id}")
                return None

            # Latest resume (order by created_at desc)
            resume = db.execute(
                select(Resume)
                .where(Resume.user_id == user.id)
                .order_by(Resume.created_at.desc())
            ).scalars().first()

            resume_path = resume.file_path if resume else None
            parsed = resume.parsed_json if (resume and resume.parsed_json) else {}

            return {
                "user_id": str(user.id),
                "name": user.full_name,
                "email": user.email,
                "preferences": {
                    "keywords": prefs.keywords,
                    "location": prefs.location,
                    "portals": prefs.portals,
                    "max_apps_per_day": prefs.max_apps_per_day,
                },
                "resume_path": resume_path,
                "parsed_resume": parsed,
                # Fields from parsed resume (populated by Phase 3 resume parser)
                "phone": parsed.get("phone", ""),
                "years_experience": parsed.get("years_experience", 3),
                "linkedin_url": parsed.get("linkedin_url", ""),
                "portfolio_url": parsed.get("portfolio_url", ""),
                "city": parsed.get("city", ""),
            }

    except Exception as e:
        logger.error(f"[job_tasks] _get_user_data error for {user_id}: {e}")
        return None


def _get_credentials(user_id: str, portal: str) -> Optional[tuple[str, str]]:
    """Fetches and decrypts portal credentials. Returns (username, password) or None."""
    try:
        from backend.models.credential import Credential
        from backend.services.credential_manager import credential_manager

        with _get_sync_session() as db:
            cred = db.execute(
                select(Credential).where(
                    Credential.user_id == uuid.UUID(user_id),
                    Credential.portal == portal,
                )
            ).scalar_one_or_none()

            if not cred:
                logger.warning(f"[job_tasks] No {portal} credentials for user {user_id}")
                return None

            username = credential_manager.decrypt(cred.enc_username)
            password = credential_manager.decrypt(cred.enc_password)
            return username, password

    except Exception as e:
        logger.error(f"[job_tasks] _get_credentials error: {e}")
        return None


def _count_todays_applications(user_id: str, portal: str) -> int:
    """Counts successful applications made today on this portal for rate limiting."""
    try:
        from backend.models.application import Application

        with _get_sync_session() as db:
            count = db.execute(
                select(func.count(Application.id)).where(
                    and_(
                        Application.user_id == uuid.UUID(user_id),
                        Application.portal == portal,
                        Application.status == "applied",
                        func.date(Application.applied_at) == date.today(),
                    )
                )
            ).scalar()
            return count or 0
    except Exception as e:
        logger.error(f"[job_tasks] _count_todays_applications error: {e}")
        return 0


def _save_application(user_id: str, result: dict) -> None:
    """Saves an ApplicationResult dict to the applications table."""
    try:
        from backend.models.application import Application

        with _get_sync_session() as db:
            app = Application(
                user_id=uuid.UUID(user_id),
                portal=result.get("portal", "unknown"),
                job_title=result.get("title", "Unknown Title"),
                company=result.get("company", "Unknown Company"),
                job_url=result.get("job_url", ""),
                job_description=result.get("description", "")[:5000],
                match_score=result.get("match_score"),
                status=result.get("status", "failed"),
                failure_reason=result.get("failure_reason", ""),
            )
            db.add(app)
            db.commit()
    except Exception as e:
        logger.error(f"[job_tasks] _save_application error: {e}")


def _update_credential_login(user_id: str, portal: str, success: bool) -> None:
    """Updates is_verified + last_login_at after a login attempt."""
    try:
        from backend.models.credential import Credential

        with _get_sync_session() as db:
            cred = db.execute(
                select(Credential).where(
                    Credential.user_id == uuid.UUID(user_id),
                    Credential.portal == portal,
                )
            ).scalar_one_or_none()

            if cred:
                cred.is_verified = success
                if success:
                    cred.last_login_at = datetime.utcnow()
                db.commit()
    except Exception as e:
        logger.error(f"[job_tasks] _update_credential_login error: {e}")


# ─── Main Task: One User, One Portal ─────────────────────────────────────────

@celery_app.task(
    name="backend.tasks.job_tasks.run_job_agent",
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    time_limit=7200,
    soft_time_limit=7000,
    queue="job_search",
)
def run_job_agent(self, user_id: str, portal: str, dry_run: bool = False) -> dict:
    """
    Main Celery task: runs the full job agent cycle for one user on one portal.

    Steps:
      1. Load user preferences + resume from DB
      2. Decrypt portal credentials
      3. Check today's application count vs daily limit
      4. Launch the correct agent (Indeed/Dice/LinkedIn)
      5. Login → Search → Apply for each job found
      6. Save every result to the applications table
      7. Return a summary

    Args:
        user_id: UUID string of the job-seeker user
        portal: 'indeed' | 'dice' | 'linkedin'
        dry_run: If True, all steps run but final Submit is NOT clicked.
                 Always use dry_run=True when testing.

    Returns:
        Summary dict with applied/failed/skipped counts.
    """
    logger.info(
        f"[job_tasks] ▶️ run_job_agent | "
        f"user={user_id[:8]}... | portal={portal} | dry_run={dry_run}"
    )

    summary = {
        "user_id": user_id,
        "portal": portal,
        "dry_run": dry_run,
        "total_found": 0,
        "applied": 0,
        "failed": 0,
        "skipped": 0,
        "error": None,
    }

    try:
        # Step 1: User data
        user_data = _get_user_data(user_id)
        if not user_data:
            summary["error"] = "user_data_not_found"
            return summary

        prefs = user_data["preferences"]

        # Step 2: Check portal is in user's list
        if portal not in prefs["portals"]:
            logger.info(f"[job_tasks] Portal '{portal}' not in user's portals — skipping")
            summary["error"] = "portal_not_configured"
            return summary

        # Step 3: Rate limit check
        todays_count = _count_todays_applications(user_id, portal)
        max_today = min(prefs["max_apps_per_day"], 50)  # Hard cap at 50

        if todays_count >= max_today:
            logger.info(
                f"[job_tasks] Daily limit reached: {todays_count}/{max_today} "
                f"for user={user_id[:8]}... on {portal}"
            )
            summary["error"] = "daily_limit_reached"
            return summary

        remaining_quota = max_today - todays_count
        logger.info(f"[job_tasks] Quota: {todays_count} used, {remaining_quota} remaining")

        # Step 4: Decrypt credentials
        creds = _get_credentials(user_id, portal)
        if not creds:
            summary["error"] = f"no_{portal}_credentials"
            return summary
        username, password = creds

        # Step 5: Run async agent
        async def _run_agent():
            if portal == "indeed":
                from backend.agents.indeed_agent import IndeedAgent as AgentClass
            elif portal == "dice":
                from backend.agents.dice_agent import DiceAgent as AgentClass
            elif portal == "linkedin":
                from backend.agents.linkedin_agent import LinkedInAgent as AgentClass
            else:
                raise ValueError(f"Unknown portal: {portal}")

            # ── Phase 3: AI Services ───────────────────────────────────────────
            from backend.services.job_matcher import JobMatcher
            from backend.services.form_filler import FormFiller
            from backend.services.cover_letter import CoverLetterGenerator

            matcher = JobMatcher()
            filler = FormFiller(
                parsed_resume=user_data.get("parsed_resume", {}),
                user_data=user_data,
            )
            cover_gen = CoverLetterGenerator()
            # ──────────────────────────────────────────────────────────────────

            async with AgentClass(user_id=user_id, headless=False) as agent:

                # Login
                logged_in = await agent.login(username, password)
                _update_credential_login(user_id, portal, logged_in)

                if not logged_in:
                    summary["error"] = "login_failed"
                    error_msg = f"Login FAILED for user={user_id[:8]}... on {portal}. Please check credentials."
                    logger.error(f"[job_tasks] {error_msg}")
                    # ── Alert on login failure ───────────────────────────────
                    _run_async(notifier.send_error_alert(
                        subject=f"Login Failed: {portal.upper()}",
                        message=error_msg
                    ))
                    return

                # Search
                jobs = await agent.search_jobs(
                    keywords=prefs["keywords"],
                    location=prefs["location"],
                    max_results=min(remaining_quota + 5, 30),
                )
                summary["total_found"] = len(jobs)
                logger.info(f"[job_tasks] Found {len(jobs)} jobs on {portal}")

                if not jobs:
                    summary["error"] = "no_jobs_found"
                    return

                # Apply
                applied_this_session = 0
                for job in jobs:
                    if applied_this_session >= remaining_quota:
                        break

                    # ── Phase 3: Score the job before applying ─────────────────
                    parsed_resume = user_data.get("parsed_resume", {})
                    job_desc = getattr(job, "description", "") or ""

                    match_result = await matcher.score(job_desc, parsed_resume)
                    logger.info(
                        f"[job_tasks] Job score={match_result.score}/100 "
                        f"'{getattr(job, 'title', '?')}' @ {getattr(job, 'company', '?')} "
                        f"({match_result.method})"
                    )

                    if not match_result.should_apply:
                        logger.info(
                            f"[job_tasks] ⏭️  SKIPPED (score {match_result.score} < threshold) "
                            f"'{getattr(job, 'title', '?')}'"
                        )
                        summary["skipped"] += 1
                        _save_application(user_id, {
                            "portal": portal,
                            "title": getattr(job, "title", ""),
                            "company": getattr(job, "company", ""),
                            "job_url": getattr(job, "url", ""),
                            "description": job_desc[:5000],
                            "match_score": match_result.score,
                            "status": "skipped",
                            "failure_reason": f"Match score {match_result.score} below threshold",
                        })
                        continue

                    # Generate cover letter for qualified jobs
                    cover_letter = await cover_gen.generate(
                        job_description=job_desc,
                        parsed_resume=parsed_resume,
                        company_name=getattr(job, "company", ""),
                        job_title=getattr(job, "title", ""),
                        user_id=user_id,
                        job_url=getattr(job, "url", ""),
                    )

                    # Attach AI context to user_data for agent use
                    enriched_user_data = {
                        **user_data,
                        "form_filler": filler,
                        "cover_letter": cover_letter,
                        "match_score": match_result.score,
                        "match_reasons": match_result.match_reasons,
                    }
                    # ──────────────────────────────────────────────────────────

                    result = await agent.apply_job(
                        job=job,
                        user_data=enriched_user_data,
                        dry_run=dry_run,
                    )

                    # Attach match score to the saved record
                    result_dict = result.to_dict()
                    result_dict["match_score"] = match_result.score
                    _save_application(user_id, result_dict)

                    if result.status == "applied":
                        summary["applied"] += 1
                        applied_this_session += 1
                    elif result.status == "failed":
                        summary["failed"] += 1
                    elif result.status == "skipped":
                        summary["skipped"] += 1

                    logger.info(
                        f"[job_tasks] [{result.status.upper()}] "
                        f"'{job.title}' @ {job.company}"
                        + (f" — {result.failure_reason}" if result.failure_reason else "")
                    )

                    # Human-like delay between applications
                    import random
                    await asyncio.sleep(random.uniform(2, 5))

        _run_async(_run_agent())

        logger.success(
            f"[job_tasks] ✅ Done | user={user_id[:8]}... | portal={portal} | "
            f"applied={summary['applied']} failed={summary['failed']} "
            f"skipped={summary['skipped']}"
        )
        return summary

    except Exception as e:
        logger.error(f"[job_tasks] run_job_agent EXCEPTION: {e}")
        summary["error"] = str(e)[:500]
        try:
            raise self.retry(exc=e, countdown=120)
        except self.MaxRetriesExceededError:
            error_msg = f"Max retries exceeded for user={user_id[:8]}... on {portal}. Task aborted."
            logger.error(f"[job_tasks] {error_msg}")
            _run_async(notifier.send_error_alert(
                subject=f"Task Failed: {portal.upper()}",
                message=error_msg
            ))
            return summary


# ─── Dispatch Task: All Active Users ─────────────────────────────────────────

@celery_app.task(
    name="backend.tasks.job_tasks.run_all_users",
    queue="job_search",
)
def run_all_users() -> dict:
    """
    Triggered by Celery Beat every 4 hours.
    Dispatches run_job_agent for every active user × their configured portals.

    Example: 3 users × 2 portals each = 6 parallel tasks dispatched.
    """
    logger.info("[job_tasks] ⏰ run_all_users triggered by Celery Beat")
    dispatched = 0

    try:
        from backend.models.user import User
        from backend.models.job_preference import JobPreference

        with _get_sync_session() as db:
            rows = db.execute(
                select(User.id, JobPreference.portals)
                .join(
                    JobPreference,
                    and_(
                        JobPreference.user_id == User.id,
                        JobPreference.is_active == True,
                    ),
                )
                .where(User.is_active == True, User.role == "job_seeker")
            ).all()

        for user_id, portals in rows:
            for portal in portals:
                run_job_agent.apply_async(
                    args=[str(user_id), portal],
                    kwargs={"dry_run": False},
                    queue="job_search",
                )
                dispatched += 1
                logger.info(f"[job_tasks] Dispatched: user={str(user_id)[:8]}... portal={portal}")

    except Exception as e:
        logger.error(f"[job_tasks] run_all_users error: {e}")

    logger.info(f"[job_tasks] ✅ Dispatched {dispatched} tasks")
    return {"dispatched": dispatched}


# ─── Resume Parse Task ────────────────────────────────────────────────────────

@celery_app.task(name="backend.tasks.job_tasks.parse_resume_task")
def parse_resume_task(resume_id: str):
    """
    Triggered after resume upload.
    Uses GPT-4o to extract structured data from the resume file. (Phase 3)
    """
    logger.info(f"[job_tasks] 📄 Parsing resume: {resume_id}")

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
                logger.error(f"[job_tasks] Resume {resume_id} not found")
                return

            parser = ResumeParser()
            raw_text, parsed_json = await parser.parse(resume.file_path, resume.file_type)
            resume.raw_text = raw_text
            resume.parsed_json = parsed_json
            resume.is_parsed = True
            await db.commit()
            logger.success(f"[job_tasks] ✅ Resume {resume_id} parsed")

    _run_async(_parse())


# ─── Daily Report Task ────────────────────────────────────────────────────────

@celery_app.task(
    name="backend.tasks.job_tasks.generate_daily_report",
    queue="reporting",
)
def generate_daily_report() -> dict:
    """
    Triggered by Celery Beat at midnight UTC.
    Summarizes today's job applications across all users and portals.
    """
    logger.info("[job_tasks] 📊 Generating daily report...")
    today = date.today()
    report = {
        "date": str(today),
        "total_applied": 0,
        "total_failed": 0,
        "total_skipped": 0,
        "by_portal": {},
    }

    try:
        from backend.models.application import Application

        with _get_sync_session() as db:
            apps = db.execute(
                select(Application).where(
                    func.date(Application.applied_at) == today
                )
            ).scalars().all()

            for app in apps:
                s = app.status
                p = app.portal
                if s == "applied":
                    report["total_applied"] += 1
                elif s == "failed":
                    report["total_failed"] += 1
                elif s == "skipped":
                    report["total_skipped"] += 1

                if p not in report["by_portal"]:
                    report["by_portal"][p] = {"applied": 0, "failed": 0, "skipped": 0}
                report["by_portal"][p][s] = report["by_portal"][p].get(s, 0) + 1

    except Exception as e:
        logger.error(f"[job_tasks] generate_daily_report error: {e}")
        report["error"] = str(e)

    logger.success(
        f"[job_tasks] 📊 Report | Applied={report['total_applied']} "
        f"Failed={report['total_failed']} Skipped={report['total_skipped']}"
    )
    return report
