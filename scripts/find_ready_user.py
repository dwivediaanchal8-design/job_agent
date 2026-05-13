import asyncio
from sqlalchemy import select
from backend.database import AsyncSessionFactory
from backend.models.user import User
from backend.models.job_preference import JobPreference
from backend.models.credential import Credential

async def find_ready_user():
    async with AsyncSessionFactory() as db:
        result = await db.execute(select(User))
        users = result.scalars().all()
        
        for user in users:
            pref_result = await db.execute(select(JobPreference).where(JobPreference.user_id == user.id))
            pref = pref_result.scalar_one_or_none()
            
            cred_result = await db.execute(select(Credential).where(Credential.user_id == user.id))
            creds = cred_result.scalars().all()
            
            if pref and creds:
                print(f"READY USER: {user.email} (ID: {user.id})")
                print(f"  Portals: {[c.portal for c in creds]}")
                print(f"  Keywords: {pref.keywords}")
                return

if __name__ == "__main__":
    asyncio.run(find_ready_user())
