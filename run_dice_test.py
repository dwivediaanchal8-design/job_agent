"""
run_dice_test.py — Full Phase 3 Dice Test
==============================================
1. Fetches user data + decrypts Dice credentials
2. Runs DiceAgent with dry_run=True to verify search and score
3. Can be toggled to dry_run=False for real application

Run: venv\\Scripts\\python.exe run_dice_test.py
"""

import asyncio
import sys
import os
import uuid

sys.stdout.reconfigure(encoding='utf-8')

RESUME_PATH = r"d:\job_agent\uploads\Aanchal_Resume.docx"

async def get_user_data_and_resume():
    """Get the job-seeker user and their parsed resume from DB."""
    from sqlalchemy import select, text
    from backend.database import SyncSessionFactory, AsyncSessionFactory
    from backend.models.resume import Resume

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

    # Fetch resume from DB
    async with AsyncSessionFactory() as db:
        existing = await db.execute(
            select(Resume)
            .where(Resume.user_id == user_id)
            .order_by(Resume.created_at.desc())
        )
        resume = existing.scalars().first()

        if not resume or not resume.parsed_json:
            print("ERROR: No parsed resume found in DB! Run run_indeed_test.py first to parse it.")
            sys.exit(1)
            
        return str(user_id), resume.parsed_json

def get_dice_credentials(user_id: str) -> tuple[str, str]:
    """Decrypt Dice credentials from DB."""
    from sqlalchemy import select
    from backend.database import SyncSessionFactory
    from backend.models.credential import Credential
    from backend.services.credential_manager import credential_manager

    print("\n[1/3] Fetching Dice credentials...")
    with SyncSessionFactory() as db:
        cred = db.execute(
            select(Credential).where(
                Credential.user_id == uuid.UUID(user_id),
                Credential.portal == "dice",
            )
        ).scalar_one_or_none()

        if not cred:
            print("ERROR: No Dice credentials found!")
            print("      Add them via add_dice_credentials.py first.")
            sys.exit(1)

        username = credential_manager.decrypt(cred.enc_username)
        password = credential_manager.decrypt(cred.enc_password)
        print(f"      Username: {username}")
        print(f"      Password: {'*' * len(password)}")
        return username, password

async def run_dice(user_id: str, username: str, password: str, parsed_json: dict):
    """Run DiceAgent: login → search → score → apply."""
    from backend.agents.dice_agent import DiceAgent
    from backend.services.job_matcher import JobMatcher
    from backend.services.form_filler import FormFiller
    from backend.services.cover_letter import CoverLetterGenerator

    print("\n[2/3] Starting Dice agent...")

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
            "keywords": ["Python", "AWS", "Developer"],
            "location": "Remote",
            "portals": ["dice"],
            "max_apps_per_day": 5,
        },
    }

    matcher = JobMatcher(threshold=40)
    filler = FormFiller(parsed_json, user_data)
    cover_gen = CoverLetterGenerator()

    applied = 0
    skipped = 0
    failed = 0
    seen_urls = set()

    async with DiceAgent(user_id=user_id, headless=False) as agent:
        # Login
        print("      Logging into Dice...")
        logged_in = await agent.login(username, password)
        if not logged_in:
            print("ERROR: Login failed!")
            # Still continue to search to test search functionality
            print("      Proceeding to search test as guest...")
        else:
            print("      Login successful!")

        # Search
        print(f"      Searching for Data Analyst jobs on Dice...")
        jobs = await agent.search_jobs(
            keywords=["Data Analyst", "SQL"],
            location="Remote",
            max_results=10,
        )

        # Deduplicate
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

        print("\n[3/3] Scoring + applying (DRY RUN) to jobs...")
        for i, job in enumerate(jobs):
            print(f"\n  Job {i+1}: '{job.title}' @ {job.company}")
            print(f"  Easy Apply: {job.is_easy_apply}")

            # Fetch description
            if not job.description:
                print(f"  Fetching job description...")
                job.description = await agent._get_job_description(job.job_url)
                print(f"  Description: {len(job.description)} chars")

            # Score
            match = await matcher.score(job.description, parsed_json)
            print(f"  Score: {match.score}/100 ({match.method}) — should_apply={match.should_apply}")
            
            if not match.should_apply:
                print(f"  SKIPPED: score {match.score} < threshold")
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
                "job_description": job.description,
            }

            # Apply (dry_run=True for safety)
            print("  Attempting Easy Apply (DRY RUN)...")
            result = await agent.apply_job(job=job, user_data=enriched, dry_run=True)
            print(f"  Result: {result.status.upper()}" + (f" — {result.failure_reason}" if result.failure_reason else ""))

            if result.status == "applied":
                applied += 1
            elif result.status == "failed":
                failed += 1
            else:
                skipped += 1

            if applied >= 2:
                print("  Tested 2 applications — stopping.")
                break

            await asyncio.sleep(2)

    print(f"\n{'='*50}")
    print(f"  DICE TEST SUMMARY (DRY RUN)")
    print(f"{'='*50}")
    print(f"  Applied (Simulated): {applied}")
    print(f"  Skipped           : {skipped}")
    print(f"  Failed            : {failed}")

async def main():
    print("="*50)
    print("  DICE AGENT — PHASE 3 VERIFICATION")
    print("="*50)

    user_id, parsed_json = await get_user_data_and_resume()
    username, password = get_dice_credentials(user_id)
    await run_dice(user_id, username, password, parsed_json)

if __name__ == "__main__":
    asyncio.run(main())
