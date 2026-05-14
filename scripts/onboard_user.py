import asyncio
import os
import sys
import uuid
from pathlib import Path

# Add project root to sys.path
root = Path(__file__).resolve().parent.parent
sys.path.append(str(root))

from sqlalchemy import select
from loguru import logger

from backend.database import AsyncSessionFactory, SyncSessionFactory
from backend.models.user import User
from backend.models.resume import Resume
from backend.models.job_preference import JobPreference
from backend.auth import hash_password
from backend.services.resume_parser import ResumeParser

# Configuration for the real user
USER_EMAIL = "dwivediaanchal8@gmail.com"
USER_NAME = "Aanchal Dwivedi"
RESUME_PATH = root / "Aanchal_Resume_Data_Analyst.docx"
KEYWORDS = ["Data Analyst", "Python Developer", "Business Intelligence", "SQL Developer"]
LOCATION = "Remote"

async def onboard():
    logger.info(f"🚀 Starting onboarding for {USER_NAME}...")

    if not RESUME_PATH.exists():
        logger.error(f"Resume file not found: {RESUME_PATH}")
        return

    async with AsyncSessionFactory() as db:
        # 1. Create or Update User
        result = await db.execute(select(User).where(User.email == USER_EMAIL))
        user = result.scalar_one_or_none()

        if user:
            logger.info(f"👤 User {USER_EMAIL} already exists. Updating...")
            user.full_name = USER_NAME
        else:
            logger.info(f"👤 Creating new user {USER_EMAIL}...")
            user = User(
                email=USER_EMAIL,
                full_name=USER_NAME,
                hashed_password=hash_password("user123"), # Default password, instruct to change
                role="job_seeker",
                is_active=True
            )
            db.add(user)
        
        await db.flush() # Get user ID
        user_id = user.id

        # 2. Parse and Save Resume
        logger.info("📄 Parsing resume...")
        parser = ResumeParser()
        raw_text, parsed_json = await parser.parse(str(RESUME_PATH), "docx")
        
        # Deactivate old resumes
        await db.execute(
            Resume.__table__.update().where(Resume.user_id == user_id).values(is_active=False)
        )

        # Check if resume record exists
        result = await db.execute(
            select(Resume).where(Resume.user_id == user_id, Resume.file_name == RESUME_PATH.name)
        )
        resume = result.scalar_one_or_none()

        if resume:
            logger.info("📄 Updating existing resume record...")
            resume.file_path = str(RESUME_PATH)
            resume.raw_text = raw_text
            resume.parsed_json = parsed_json
            resume.is_active = True
            resume.is_parsed = True
        else:
            logger.info("📄 Creating new resume record...")
            resume = Resume(
                user_id=user_id,
                file_name=RESUME_PATH.name,
                file_path=str(RESUME_PATH),
                file_type="docx",
                raw_text=raw_text,
                parsed_json=parsed_json,
                is_active=True,
                is_parsed=True
            )
            db.add(resume)

        # 3. Create or Update Job Preferences
        result = await db.execute(select(JobPreference).where(JobPreference.user_id == user_id))
        prefs = result.scalar_one_or_none()

        if prefs:
            logger.info("⚙️ Updating job preferences...")
            prefs.keywords = KEYWORDS
            prefs.location = LOCATION
            prefs.portals = ["dice", "indeed"] # Default portals
            prefs.is_active = True
        else:
            logger.info("⚙️ Creating job preferences...")
            prefs = JobPreference(
                user_id=user_id,
                keywords=KEYWORDS,
                location=LOCATION,
                portals=["dice", "indeed"],
                is_active=True
            )
            db.add(prefs)

        await db.commit()
        logger.success(f"✅ Onboarding complete for {USER_NAME}!")
        logger.info(f"User ID: {user_id}")
        logger.info(f"Portal: http://localhost:3000")
        logger.info(f"Instructions: Please log in as admin@jobagent.ai (pass: admin123) and add {USER_NAME}'s portal credentials.")

if __name__ == "__main__":
    asyncio.run(onboard())
