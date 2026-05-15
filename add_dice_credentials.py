"""
add_dice_credentials.py — Adds Dice.com credentials for Aanchal's account
"""
import asyncio, sys
sys.stdout.reconfigure(encoding='utf-8')

DICE_USERNAME = "dwivediaanchal8@gmail.com"
DICE_PASSWORD = ".5TU*m8yvfK,dMM"

async def main():
    from sqlalchemy import select, text
    from backend.database import AsyncSessionFactory, SyncSessionFactory
    from backend.models.credential import Credential
    from backend.services.credential_manager import credential_manager

    # Get job-seeker user ID
    with SyncSessionFactory() as db:
        row = db.execute(
            text("SELECT id FROM users WHERE email='dwivediaanchal8@gmail.com' LIMIT 1")
        ).fetchone()
        if not row:
            print("ERROR: User dwivediaanchal8@gmail.com not found!")
            return
        user_id = row.id
        print(f"User ID: {user_id}")

    # Encrypt credentials
    enc_username = credential_manager.encrypt(DICE_USERNAME)
    enc_password = credential_manager.encrypt(DICE_PASSWORD)
    print(f"Encrypted username: {enc_username[:30]}...")
    print(f"Encrypted password: {enc_password[:30]}...")

    # Upsert Dice credentials
    async with AsyncSessionFactory() as db:
        existing = await db.execute(
            select(Credential).where(
                Credential.user_id == user_id,
                Credential.portal == "dice",
            )
        )
        cred = existing.scalars().first()

        if cred:
            print("Updating existing Dice credential...")
            cred.enc_username = enc_username
            cred.enc_password = enc_password
            cred.is_verified = False
        else:
            print("Creating new Dice credential...")
            cred = Credential(
                user_id=user_id,
                portal="dice",
                enc_username=enc_username,
                enc_password=enc_password,
                is_verified=False,
            )
            db.add(cred)

        await db.commit()
        print("Dice credentials saved!")

    # Verify round-trip decryption
    with SyncSessionFactory() as db:
        row = db.execute(
            text("SELECT enc_username, enc_password FROM credentials WHERE portal='dice' LIMIT 1")
        ).fetchone()
        if row:
            dec_u = credential_manager.decrypt(row.enc_username)
            dec_p = credential_manager.decrypt(row.enc_password)
            ok = dec_u == DICE_USERNAME and dec_p == DICE_PASSWORD
            print(f"\nDecryption check: {'PASS' if ok else 'FAIL'}")
            print(f"  Username: {dec_u}")
            print(f"  Password: {'*' * len(dec_p)}")

asyncio.run(main())
