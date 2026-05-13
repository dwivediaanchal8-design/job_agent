import asyncio
import uuid
from backend.database import AsyncSessionFactory
from backend.models.user import User
from backend.models.job_preference import JobPreference
from backend.models.credential import Credential
from backend.auth import hash_password

async def bootstrap():
    async with AsyncSessionFactory() as db:
        # 1. Create Admin
        admin = User(
            email="admin@jobagent.com",
            full_name="Admin User",
            hashed_password=hash_password("Password123!"),
            role="admin"
        )
        db.add(admin)
        
        # 2. Create Test User
        user = User(
            email="testuser@example.com",
            full_name="Test Seeker",
            hashed_password=hash_password("Password123!"),
            role="job_seeker"
        )
        db.add(user)
        await db.flush()
        
        # 3. Add Preferences
        pref = JobPreference(
            user_id=user.id,
            keywords=["Software Developer Intern", "Python Developer"],
            location="Remote",
            job_type="full_time",
            portals=["indeed"]
        )
        db.add(pref)
        
        # 4. Add Dummy Credentials (user must update these for real apply)
        from backend.services.credential_manager import credential_manager
        cred = Credential(
            user_id=user.id,
            portal="indeed",
            enc_username=credential_manager.encrypt("dummy_user"),
            enc_password=credential_manager.encrypt("dummy_password")
        )
        db.add(cred)
        
        await db.commit()
        print("✅ Bootstrap complete. Created admin and testuser.")

if __name__ == "__main__":
    asyncio.run(bootstrap())
