import asyncio
import json
from backend.database import AsyncSessionFactory
from backend.models.resume import Resume
from sqlalchemy import select

async def check_resume():
    async with AsyncSessionFactory() as db:
        res = await db.execute(
            select(Resume).where(Resume.user_id == '6ec578a7-4e3d-4b83-9cc1-988632ae7727')
        )
        resume = res.scalars().first()
        if resume:
            print(json.dumps(resume.parsed_json, indent=2))
        else:
            print("No resume found for user.")

if __name__ == "__main__":
    asyncio.run(check_resume())
