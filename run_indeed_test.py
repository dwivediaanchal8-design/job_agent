"""
run_indeed_test.py — Full Phase 3 Indeed Test
==============================================
1. Upserts Aanchal_Resume.docx into DB with parsed JSON
2. Fetches user data + decrypts Indeed credentials
3. Runs IndeedAgent with dry_run=False to actually apply

Run: venv\Scripts\python.exe run_indeed_test.py
"""

import asyncio
import sys
import os
import uuid

sys.stdout.reconfigure(encoding='utf-8')

RESUME_PATH = r"d:\job_agent\uploads\Aanchal_Resume.docx"
USER_ID_STR = "fed31086-0000-0000-0000-000000000000"  # placeholder, resolved below


async def step1_save_resume():
    """Parse + save resume to DB for the job-seeker user."""
    from sqlalchemy import select, text
    from backend.database import SyncSessionFactory, AsyncSessionFactory
    from backend.models.resume import Resume
    from backend.services.resume_parser import ResumeParser

    print("\n[1/4] Parsing resume with GPT-4o...")
    parser = ResumeParser()
    raw_text, parsed_json = await parser.parse(RESUME_PATH, "docx")
    print(f"      Name   : {parsed_json.get('name')}")
    print(f"      Email  : {parsed_json.get('email')}")
    print(f"      Skills : {', '.join(parsed_json.get('skills', []))}")

    # Get the job-seeker user ID
    with SyncSessionFactory() as db:
        row = db.execute(
            text("SELECT id FROM users WHERE role='job_seeker' AND is_active=true LIMIT 1")
        ).fetchone()
        if not row:
            print("ERROR: No active job-seeker user found in DB!")
            sys.exit(1)
        user_id = row.id
        print(f"      User ID: {user_id}")

    # Save/update resume in DB
    async with AsyncSessionFactory() as db:
        # Check if resume already exists
        existing = await db.execute(
            select(Resume)
            .where(Resume.user_id == user_id)
            .order_by(Resume.created_at.desc())
        )
        resume = existing.scalars().first()

        if resume:
            print("      Updating existing resume record...")
            resume.file_path = RESUME_PATH
            resume.file_name = os.path.basename(RESUME_PATH)
            resume.file_type = "docx"
            resume.raw_text = raw_text
            resume.parsed_json = parsed_json
            resume.is_parsed = True
            resume.is_active = True
        else:
            print("      Creating new resume record...")
            resume = Resume(
                user_id=user_id,
                file_name=os.path.basename(RESUME_PATH),
                file_path=RESUME_PATH,
                file_type="docx",
                raw_text=raw_text,
                parsed_json=parsed_json,
                is_parsed=True,
                is_active=True,
            )
            db.add(resume)

        await db.commit()
        print("      Resume saved to DB!")

    return str(user_id), parsed_json


def step2_get_credentials(user_id: str) -> tuple[str, str]:
    """Decrypt Indeed credentials from DB."""
    from sqlalchemy import select
    from backend.database import SyncSessionFactory
    from backend.models.credential import Credential
    from backend.services.credential_manager import credential_manager

    print("\n[2/4] Fetching Indeed credentials...")
    with SyncSessionFactory() as db:
        cred = db.execute(
            select(Credential).where(
                Credential.user_id == uuid.UUID(user_id),
                Credential.portal == "indeed",
            )
        ).scalar_one_or_none()

        if not cred:
            print("ERROR: No Indeed credentials found!")
            print("      Add them via POST /credentials API first.")
            sys.exit(1)

        username = credential_manager.decrypt(cred.enc_username)
        password = credential_manager.decrypt(cred.enc_password)
        print(f"      Username: {username}")
        print(f"      Password: {'*' * len(password)}")
        return username, password


async def step3_run_indeed(user_id: str, username: str, password: str, parsed_json: dict):
    """Run IndeedAgent: login → search → score → apply."""
    from backend.agents.indeed_agent import IndeedAgent
    from backend.services.job_matcher import JobMatcher
    from backend.services.form_filler import FormFiller
    from backend.services.cover_letter import CoverLetterGenerator

    print("\n[3/4] Starting Indeed agent...")

    user_data = {
        "user_id": user_id,
        "name": parsed_json.get("name", "Aanchal Dwivedi"),
        "email": parsed_json.get("email", ""),
        "phone": parsed_json.get("phone", ""),
        "resume_path": RESUME_PATH,
        "parsed_resume": parsed_json,
        "years_experience": int(parsed_json.get("total_years_experience", 0)),
        "linkedin_url": parsed_json.get("linkedin_url", ""),
        "city": "Remote",
        "preferences": {
            "keywords": ["Python Intern", "Data Analyst Intern"],
            "location": "Remote",
            "portals": ["indeed"],
            "max_apps_per_day": 5,
        },
    }

    matcher = JobMatcher(threshold=40)  # Lower threshold - intern with no experience
    filler = FormFiller(parsed_json, user_data)
    cover_gen = CoverLetterGenerator()

    applied = 0
    skipped = 0
    failed = 0
    seen_urls = set()  # Deduplicate job URLs

    async with IndeedAgent(user_id=user_id, headless=False) as agent:
        # Login
        print("      Logging into Indeed...")
        logged_in = await agent.login(username, password)
        if not logged_in:
            print("ERROR: Login failed!")
            return

        print("      Login successful!")

        # Search on India Indeed with Indeed Apply filter (iafc=1)
        print("      Searching for Python intern jobs with Indeed Apply...")
        jobs = await agent.search_jobs(
            keywords=["Python intern", "data analyst intern"],
            location="Remote",
            max_results=20,
        )

        # Deduplicate by URL
        unique_jobs = []
        for j in jobs:
            if j.job_url not in seen_urls:
                seen_urls.add(j.job_url)
                unique_jobs.append(j)
        jobs = unique_jobs
        print(f"      Found {len(jobs)} unique jobs")

        if not jobs:
            print("      No jobs found.")
            return

        print("\n[4/4] Scoring + applying to jobs...")
        for i, job in enumerate(jobs):
            print(f"\n  Job {i+1}: '{job.title}' @ {job.company}")
            print(f"  Easy Apply: {job.is_easy_apply}")

            # IMPORTANT: Fetch full job description from job page before scoring
            if not job.description:
                print(f"  Fetching job description...")
                job.description = await agent._get_job_description(job.job_url)
                print(f"  Description: {len(job.description)} chars")

            # Score the job with real description
            match = await matcher.score(job.description, parsed_json)
            print(f"  Score: {match.score}/100 ({match.method}) — should_apply={match.should_apply}")
            if match.match_reasons:
                print(f"  Reasons: {', '.join(match.match_reasons[:2])}")

            if not match.should_apply:
                print(f"  SKIPPED: score {match.score} < threshold")
                skipped += 1
                continue

            if not job.is_easy_apply:
                print(f"  SKIPPED: not an Indeed Apply job")
                skipped += 1
                continue

            # Generate cover letter
            cover_letter = await cover_gen.generate(
                job_description=job.description,
                parsed_resume=parsed_json,
                company_name=job.company,
                job_title=job.title,
                user_id=user_id,
                job_url=job.job_url,
            )
            print(f"  Cover letter: {len(cover_letter.split())} words generated")

            enriched = {
                **user_data,
                "form_filler": filler,
                "cover_letter": cover_letter,
                "match_score": match.score,
            }

            # Apply (dry_run=False = real submission)
            result = await agent.apply_job(job=job, user_data=enriched, dry_run=False)
            print(f"  Result: {result.status.upper()}" + (f" — {result.failure_reason}" if result.failure_reason else ""))

            if result.status == "applied":
                applied += 1
            elif result.status == "failed":
                failed += 1
            else:
                skipped += 1

            if applied >= 3:
                print("  Reached 3 applications — stopping.")
                break

            await asyncio.sleep(3)

    print(f"\n{'='*50}")
    print(f"  SESSION SUMMARY")
    print(f"{'='*50}")
    print(f"  Applied : {applied}")
    print(f"  Skipped : {skipped}")
    print(f"  Failed  : {failed}")


async def main():
    print("="*50)
    print("  INDEED AGENT — PHASE 3 LIVE TEST")
    print("="*50)

    user_id, parsed_json = await step1_save_resume()
    username, password = step2_get_credentials(user_id)
    await step3_run_indeed(user_id, username, password, parsed_json)


if __name__ == "__main__":
    asyncio.run(main())
