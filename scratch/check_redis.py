
import redis
import os
from dotenv import load_dotenv

load_dotenv()

def check_redis():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    print(f"Connecting to Redis at {redis_url}...")
    try:
        r = redis.from_url(redis_url)
        r.ping()
        print("✅ Redis is running and accessible.")
        return True
    except Exception as e:
        print(f"❌ Redis is NOT running or accessible: {e}")
        return False

if __name__ == "__main__":
    check_redis()
