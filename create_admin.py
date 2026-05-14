import sys
sys.stdout.reconfigure(encoding='utf-8')
from backend.database import SyncSessionFactory
from backend.models.user import User
from backend.auth import hash_password
from sqlalchemy import select

def create_admin():
    email = "admin@jobagent.ai"
    password = "admin123"
    name = "System Administrator"
    
    with SyncSessionFactory() as db:
        # Check if already exists
        existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if existing:
            print(f"Admin user {email} already exists.")
            return
        
        new_user = User(
            email=email,
            full_name=name,
            hashed_password=hash_password(password),
            role="admin",
            is_active=True
        )
        db.add(new_user)
        db.commit()
        print(f"✅ Admin user created successfully!")
        print(f"  Email: {email}")
        print(f"  Password: {password}")

if __name__ == "__main__":
    create_admin()
