"""
real_run_dice.py — Real Autonomous Job Application for Dice
==========================================================
1. Fetches dwivediaanchal8@gmail.com data + decrypts Dice credentials
2. Runs DiceAgent with dry_run=False for REAL application
3. Applies to matching jobs automatically.

Run: $env:PYTHONPATH="."; .\venv\Scripts\python.exe real_run_dice.py
"""

import asyncio
import sys
import os
import uuid
from sqlalchemy import select, text
from backend.database import SyncSessionFactory, AsyncSessionFactory
from backend.models.resume import Resume
from backend.models.user import User
from backend.models.credential import Credential
from backend.services.credential_manager import credential_manager
from backend.agents.dice_agent import DiceAgent
from backend.services.job_matcher import JobMatcher
from backend.services.form_filler import FormFiller
from backend.services.cover_letter import CoverLetterGenerator

sys.stdout.reconfigure(encoding='utf-8')

# Constants
TARGET_EMAIL = "dwivediaanchal8@gmail.com"
RESUME_PATH = r"d:\job_agent\uploads\Aanchal_Resume_Data_Analyst.docx"

async def get_user_data_and_resume():
    print(f"\n[1/4] Fetching data for {TARGET_EMAIL}...")
    
    with SyncSessionFactory() as db:
        user = db.execute(
            select(User).where(User.email == TARGET_EMAIL)
        ).scalar_one_or_none()
        
        if not user:
            print(f"ERROR: User {TARGET_EMAIL} not found!")
            sys.exit(1)
        
        user_id = user.id
        print(f"      User ID: {user_id}")

    async with AsyncSessionFactory() as db:
        existing = await db.execute(
            select(Resume)
            .where(Resume.user_id == user_id)
            .order_by(Resume.created_at.desc())
        )
        resume = existing.scalars().first()

        if not resume or not resume.parsed_json:
            print("ERROR: No parsed resume found in DB!")
            sys.exit(1)
            
        return str(user_id), resume.parsed_json

def get_dice_credentials(user_id: str) -> tuple[str, str]:
    print("\n[2/4] Fetching Dice credentials...")
    with SyncSessionFactory() as db:
        cred = db.execute(
            select(Credential).where(
                Credential.user_id == uuid.UUID(user_id),
                Credential.portal == "dice",
            )
        ).scalar_one_or_none()

        if not cred:
            print("ERROR: No Dice credentials found for this user!")
            sys.exit(1)

        username = credential_manager.decrypt(cred.enc_username)
        password = credential_manager.decrypt(cred.enc_password)
        print(f"      Username: {username}")
        return username, password

async def run_dice(user_id: str, username: str, password: str, parsed_json: dict):
    print("\n[3/4] Starting Dice agent for REAL application...")

    user_data = {
        "user_id": user_id,
        "name": parsed_json.get("name", "Aanchal Dwivedi"),
        "email": TARGET_EMAIL,
        "phone": parsed_json.get("phone", ""),
        "resume_path": RESUME_PATH,
        "parsed_resume": parsed_json,
        "years_experience": int(parsed_json.get("total_years_experience", 5)),
        "linkedin_url": parsed_json.get("linkedin_url", ""),
        "city": "Remote",
        "preferences": {
            "keywords": ["Data Analyst", "SQL", "Python", "Tableau"],
            "location": "Remote",
            "portals": ["dice"],
            "max_apps_per_day": 5,
        },
    }

    matcher = JobMatcher(threshold=70) # Higher threshold for real applications
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
            print("ERROR: Login failed! Cannot apply without login.")
            return

        # Search
        keywords = user_data["preferences"]["keywords"]
        print(f"      Searching for {keywords} jobs on Dice...")
        jobs = await agent.search_jobs(
            keywords=keywords,
            location="Remote",
            max_results=15,
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

        print("\n[4/4] Scoring + REAL APPLYING to jobs...")
        for i, job in enumerate(jobs):
            print(f"\n  Job {i+1}: '{job.title}' @ {job.company}")
            
            # Fetch description if missing
            if not job.description:
                job.description = await agent.get_job_description(job.job_url)

            # Score
            match = await matcher.score(job.description, parsed_json)
            print(f"  Score: {match.score}/100 — should_apply={match.should_apply}")
            
            if not match.should_apply:
                print(f"  SKIPPED: score {match.score} < threshold")
                skipped += 1
                continue

            if not job.is_easy_apply:
                print(f"  SKIPPED: Not an Easy Apply job.")
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

            enriched = {
                **user_data,
                "form_filler": filler,
                "cover_letter": cover_letter,
                "match_score": match.score,
                "job_description": job.description,
            }

            # REAL APPLY
            print("  Attempting REAL Easy Apply...")
            result = await agent.apply_job(job=job, user_data=enriched, dry_run=False)
            print(f"  Result: {result.status.upper()}" + (f" — {result.failure_reason}" if result.failure_reason else ""))

            if result.status == "applied":
                applied += 1
            elif result.status == "failed":
                failed += 1
            else:
                skipped += 1

            # Limit to 5 per run for safety
            if applied >= 5:
                print("  Reached max applications (5) — stopping.")
                break

            await asyncio.sleep(5)

    print(f"\n{'='*50}")
    print(f"  REAL RUN SUMMARY")
    print(f"{'='*50}")
    print(f"  Applied (REAL)   : {applied}")
    print(f"  Skipped          : {skipped}")
    print(f"  Failed           : {failed}")

async def main():
    print("="*50)
    print("  DICE AGENT — REAL APPLICATION RUN")
    print("="*50)

    user_id, parsed_json = await get_user_data_and_resume()
    username, password = get_dice_credentials(user_id)
    await run_dice(user_id, username, password, parsed_json)

if __name__ == "__main__":
    asyncio.run(main())
