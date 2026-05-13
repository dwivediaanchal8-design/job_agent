import sys
sys.stdout.reconfigure(encoding='utf-8')
from backend.database import SyncSessionFactory
from sqlalchemy import text

with SyncSessionFactory() as db:
    creds = db.execute(text("SELECT user_id, portal FROM credentials")).fetchall()
    print("All credentials:")
    for c in creds:
        print(f"  portal={c.portal}  user={str(c.user_id)[:8]}...")
    prefs = db.execute(text("SELECT keywords, location, portals FROM job_preferences WHERE is_active=true LIMIT 1")).fetchall()
    print("Preferences:")
    for p in prefs:
        print(f"  keywords={p.keywords}  location={p.location}  portals={p.portals}")
