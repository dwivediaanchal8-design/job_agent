import asyncio
from sqlalchemy import select, text
from backend.database import SyncSessionFactory, AsyncSessionFactory
from backend.models.user import User
from backend.models.resume import Resume
from backend.models.credential import Credential

async def check_data():
    print("--- Users ---")
    with SyncSessionFactory() as db:
        users = db.execute(select(User)).scalars().all()
        for u in users:
            print(f"User: {u.email}, Role: {u.role}, ID: {u.id}")

    print("\n--- Resumes ---")
    async with AsyncSessionFactory() as db:
        resumes = (await db.execute(select(Resume))).scalars().all()
        for r in resumes:
            print(f"Resume ID: {r.id}, User ID: {r.user_id}, Parsed: {bool(r.parsed_json)}")

    print("\n--- Credentials ---")
    with SyncSessionFactory() as db:
        creds = db.execute(select(Credential)).scalars().all()
        for c in creds:
            print(f"Cred ID: {c.id}, User ID: {c.user_id}, Portal: {c.portal}")

if __name__ == "__main__":
    asyncio.run(check_data())
