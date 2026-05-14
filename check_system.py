import sys
import asyncio
import uuid
from loguru import logger
from sqlalchemy import select

# Reconfigure stdout for UTF-8 support on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from backend.database import SyncSessionFactory
from backend.models.user import User
from backend.models.credential import Credential
from backend.models.resume import Resume
from backend.models.job_preference import JobPreference
from backend.tasks.job_tasks import run_job_agent

def check_system_integration():
    print("====================================================")
    print("🚀 JOB AGENT SYSTEM INTEGRATION CHECK")
    print("====================================================\n")

    # 1. Check Database
    print("[1] Database Connectivity & Models:")
    try:
        with SyncSessionFactory() as db:
            user_count = db.query(User).count()
            print(f"  ✅ Database connection OK. Found {user_count} users.")
    except Exception as e:
        print(f"  ❌ Database connection FAILED: {e}")
        return

    # 2. Check Admin User
    print("\n[2] System Administrator:")
    try:
        with SyncSessionFactory() as db:
            admin = db.execute(select(User).where(User.role == 'admin')).scalars().first()
            if admin:
                print(f"  ✅ Admin user found: {admin.email}")
            else:
                print("  ⚠️ No admin user found! Run create_admin.py")
    except Exception as e:
        print(f"  ❌ Admin check failed: {e}")

    # 3. Check AI Services (Simulation)
    print("\n[3] AI Services Connectivity:")
    try:
        from backend.services.openai_client import get_client
        client = get_client()
        if client:
            print("  ✅ AI Client initialized (OpenRouter/OpenAI)")
        else:
            print("  ⚠️ AI Client NOT configured. System will use keyword fallbacks.")
    except Exception as e:
        print(f"  ❌ AI Client check failed: {e}")

    # 4. Check Celery / Redis
    print("\n[4] Backend Task Queue (Redis):")
    try:
        from backend.tasks.celery_app import celery_app
        # We don't want to hang if no worker is running
        print("  Checking for workers...")
        # celery_app.control.ping() can hang if no broker. 
        # We just check if we can connect to the broker.
        celery_app.connection().connect()
        print("  ✅ Redis connection OK.")
    except Exception as e:
        print(f"  ⚠️ Redis connection FAILED: {e}")

    # 5. Check Frontend
    print("\n[5] UI Access:")
    print("  👉 Dashboard: http://localhost:3000")
    print("  👉 Login:     http://localhost:3000/login")
    
    print("\n====================================================")
    print("✅ INTEGRATION CHECK COMPLETE")
    print("====================================================")

if __name__ == "__main__":
    check_system_integration()
