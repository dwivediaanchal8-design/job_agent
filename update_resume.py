import asyncio
import sys
import os
from sqlalchemy import select, text
from backend.database import SyncSessionFactory, AsyncSessionFactory
from backend.models.resume import Resume
from backend.services.resume_parser import ResumeParser

RESUME_PATH = r"d:\job_agent\uploads\Aanchal_Resume_Data_Analyst.docx"

async def main():
    print(f"Parsing resume: {RESUME_PATH}")
    parser = ResumeParser()
    raw_text, parsed_json = await parser.parse(RESUME_PATH, "docx")
    
    print("\nParsed Data:")
    print(f"Name: {parsed_json.get('name')}")
    print(f"Email: {parsed_json.get('email')}")
    print(f"Skills: {', '.join(parsed_json.get('skills', []))}")

    # Get job-seeker user
    with SyncSessionFactory() as db:
        row = db.execute(
            text("SELECT id FROM users WHERE email='dwivediaanchal8@gmail.com' LIMIT 1")
        ).fetchone()
        if not row:
            print("ERROR: User dwivediaanchal8@gmail.com not found!")
            return
        user_id = row.id

    # Update/Save in DB
    async with AsyncSessionFactory() as db:
        existing = await db.execute(
            select(Resume).where(Resume.user_id == user_id)
        )
        resume = existing.scalars().first()
        
        if resume:
            print("Updating existing resume...")
            resume.file_path = RESUME_PATH
            resume.file_name = os.path.basename(RESUME_PATH)
            resume.raw_text = raw_text
            resume.parsed_json = parsed_json
            resume.is_active = True
        else:
            print("Creating new resume record...")
            resume = Resume(
                user_id=user_id,
                file_name=os.path.basename(RESUME_PATH),
                file_path=RESUME_PATH,
                file_type="docx",
                raw_text=raw_text,
                parsed_json=parsed_json,
                is_parsed=True,
                is_active=True
            )
            db.add(resume)
            
        await db.commit()
        print("Resume updated in database!")

if __name__ == "__main__":
    asyncio.run(main())
