import asyncio
from sqlalchemy import select, func
from backend.database import AsyncSessionFactory, engine
from backend.models.application import Application

async def check_applications():
    async with AsyncSessionFactory() as db:
        # Total count
        total_result = await db.execute(select(func.count(Application.id)))
        total = total_result.scalar()
        
        # Recent applications
        recent_result = await db.execute(
            select(Application).order_by(Application.applied_at.desc()).limit(5)
        )
        recent = recent_result.scalars().all()
        
        print(f"Total Applications in DB: {total}")
        print("\nRecent Activity:")
        if not recent:
            print("No applications found yet.")
        for app in recent:
            print(f"- [{app.applied_at}] {app.portal.upper()}: {app.job_title} @ {app.company} | Status: {app.status}")
            if app.failure_reason:
                print(f"  Reason: {app.failure_reason}")

if __name__ == "__main__":
    asyncio.run(check_applications())
