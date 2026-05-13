import asyncio
from sqlalchemy import select
from backend.database import AsyncSessionFactory
from backend.models.user import User
from backend.models.resume import Resume

async def check_resume_parse():
    async with AsyncSessionFactory() as db:
        result = await db.execute(select(User).where(User.email == "testuser@example.com"))
        user = result.scalar_one_or_none()
        if not user:
            print("User not found.")
            return
            
        rs = await db.execute(select(Resume).where(Resume.user_id == user.id))
        resumes = rs.scalars().all()
        for r in resumes:
            print(f"Resume: {r.file_name}, Parsed: {r.is_parsed}")
            if not r.is_parsed:
                print("Triggering parse...")
                from backend.services.resume_parser import resume_parser
                # This needs raw text
                if not r.raw_text:
                    print("Extracting raw text...")
                    import os
                    from backend.services.resume_parser import ResumeParser
                    parser = ResumeParser()
                    r.raw_text = await parser._extract_text(r.file_path)
                
                print("Parsing with AI...")
                r.parsed_json = await resume_parser.parse(r.raw_text)
                r.is_parsed = True
                await db.commit()
                print("✅ Parse complete.")

if __name__ == "__main__":
    asyncio.run(check_resume_parse())
