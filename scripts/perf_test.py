"""
scripts/perf_test.py — Performance Testing Script
==================================================
Simulates multiple concurrent users performing API actions.
"""

import asyncio
import time
import uuid
import httpx
from loguru import logger

BASE_URL = "http://localhost:8000"
CONCURRENT_USERS = 10

async def simulate_user(user_index):
    """
    Simulates a single user registration and login.
    """
    email = f"perf_{user_index}_{uuid.uuid4().hex[:6]}@example.com"
    password = "Password123!"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Register
        start = time.perf_counter()
        try:
            reg_resp = await client.post(
                f"{BASE_URL}/auth/register",
                json={
                    "email": email,
                    "password": password,
                    "full_name": f"Perf User {user_index}",
                    "role": "job_seeker"
                }
            )
            reg_time = time.perf_counter() - start
            
            if reg_resp.status_code == 201:
                logger.info(f"User {user_index} registered in {reg_time:.4f}s")
            else:
                logger.error(f"User {user_index} registration FAILED: {reg_resp.status_code}")
                return

            # 2. Login
            start = time.perf_counter()
            login_resp = await client.post(
                f"{BASE_URL}/auth/login",
                json={"email": email, "password": password}
            )
            login_time = time.perf_counter() - start
            
            if login_resp.status_code == 200:
                logger.success(f"User {user_index} logged in in {login_time:.4f}s")
            else:
                logger.error(f"User {user_index} login FAILED: {login_resp.status_code}")

        except Exception as e:
            logger.error(f"User {user_index} encountered error: {e}")

async def run_load_test():
    logger.info(f"🚀 Starting load test with {CONCURRENT_USERS} concurrent users...")
    start_time = time.perf_counter()
    
    tasks = [simulate_user(i) for i in range(CONCURRENT_USERS)]
    await asyncio.gather(*tasks)
    
    total_time = time.perf_counter() - start_time
    logger.info(f"🏁 Load test complete in {total_time:.2f}s")

if __name__ == "__main__":
    # Ensure the server is running before starting the test!
    # Tip: Run uvicorn backend.main:app in a separate terminal.
    asyncio.run(run_load_test())
