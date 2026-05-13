import asyncio
from sqlalchemy import select
from backend.database import AsyncSessionFactory
from backend.models.user import User
from backend.models.job_preference import JobPreference
from backend.models.credential import Credential

async def check_users():
    async with AsyncSessionFactory() as db:
        result = await db.execute(select(User))
        users = result.scalars().all()
        
        print(f"Total Users: {len(users)}")
        for user in users:
            print(f"\nUser: {user.email} (ID: {user.id})")
            print(f"  Role: {user.role}, Active: {user.is_active}")
            
            # Check preferences
            pref_result = await db.execute(select(JobPreference).where(JobPreference.user_id == user.id))
            pref = pref_result.scalar_one_or_none()
            if pref:
                print(f"  Preferences: Keywords={pref.keywords}, Location={pref.location}")
            else:
                print("  Preferences: NONE")
            
            # Check credentials
            cred_result = await db.execute(select(Credential).where(Credential.user_id == user.id))
            creds = cred_result.scalars().all()
            print(f"  Credentials: {[c.portal for c in creds]}")

if __name__ == "__main__":
    asyncio.run(check_users())
