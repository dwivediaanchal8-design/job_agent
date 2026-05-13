import asyncio
from sqlalchemy import select
from backend.database import AsyncSessionFactory
from backend.models.user import User
from backend.models.resume import Resume

async def check_user_resume():
    async with AsyncSessionFactory() as db:
        result = await db.execute(select(User).where(User.email == "testuser@example.com"))
        user = result.scalar_one_or_none()
        if not user:
            print("User not found.")
            return
            
        rs = await db.execute(select(Resume).where(Resume.user_id == user.id))
        resumes = rs.scalars().all()
        print(f"Resumes: {[r.file_name for r in resumes]}")
        
        if not resumes:
            # Try to associate one if it exists in DB but maybe user_id is different?
            # Or just create one from the files in uploads/
            print("Creating resume record for testuser...")
            import os
            resume_path = "d:/job_agent/uploads/Aanchal_Resume.docx"
            if os.path.exists(resume_path):
                new_resume = Resume(
                    user_id=user.id,
                    file_name="Aanchal_Resume.docx",
                    file_path=resume_path,
                    is_active=True
                )
                db.add(new_resume)
                await db.commit()
                print("✅ Associated Aanchal_Resume.docx with testuser.")
            else:
                print("❌ Resume file not found in uploads/.")

if __name__ == "__main__":
    asyncio.run(check_user_resume())
