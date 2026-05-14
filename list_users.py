import sys
sys.stdout.reconfigure(encoding='utf-8')
from backend.database import SyncSessionFactory
from sqlalchemy import text

with SyncSessionFactory() as db:
    users = db.execute(text("SELECT id, email, full_name, role FROM users")).fetchall()
    print("Registered Users:")
    for u in users:
        print(f"  ID: {u.id} | Email: {u.email} | Name: {u.full_name} | Role: {u.role}")
