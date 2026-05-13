import asyncio
from sqlalchemy import select
from backend.database import AsyncSessionFactory
from backend.models.user import User
from backend.models.credential import Credential
from backend.services.credential_manager import credential_manager

async def check_creds():
    async with AsyncSessionFactory() as db:
        result = await db.execute(select(User).where(User.email == "testuser@example.com"))
        user = result.scalar_one_or_none()
        if not user:
            print("User not found.")
            return
            
        cred_result = await db.execute(select(Credential).where(Credential.user_id == user.id))
        creds = cred_result.scalars().all()
        
        for c in creds:
            try:
                username = credential_manager.decrypt(c.enc_username)
                print(f"Portal: {c.portal}, Username: {username}")
            except Exception as e:
                print(f"Portal: {c.portal}, Decryption Failed: {e}")

if __name__ == "__main__":
    asyncio.run(check_creds())
