import pytest
import uuid

@pytest.mark.asyncio
async def test_health_check(client):
    """Test the health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

@pytest.mark.asyncio
async def test_auth_flow(client):
    """Test register and login flow."""
    # 1. Register a new user
    email = f"test_{uuid.uuid4().hex[:6]}@example.com"
    reg_payload = {
        "email": email,
        "password": "Password123!",
        "full_name": "Test User",
        "role": "admin"
    }
    # Note: create_user requires admin, but for tests we might need to bypass or create the first admin.
    # Let's check backend/api/auth.py for register endpoint.
    response = await client.post("/auth/register", json=reg_payload)
    assert response.status_code == 201
    
    # 2. Login
    login_payload = {
        "email": email,
        "password": "Password123!"
    }
    response = await client.post("/auth/login", json=login_payload)
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    return token_data["access_token"]

@pytest.mark.asyncio
async def test_user_management(client):
    """Test admin user management."""
    token = await test_auth_flow(client)
    headers = {"Authorization": f"Bearer {token}"}
    
    # List users
    response = await client.get("/users", headers=headers)
    assert response.status_code == 200
    assert "users" in response.json()
    
    # Create a job seeker
    seeker_email = f"seeker_{uuid.uuid4().hex[:6]}@example.com"
    seeker_payload = {
        "email": seeker_email,
        "password": "Password123!",
        "full_name": "Job Seeker",
        "role": "job_seeker"
    }
    response = await client.post("/users", json=seeker_payload, headers=headers)
    assert response.status_code == 201
    seeker_id = response.json()["id"]
    
    # Deactivate seeker
    response = await client.patch(f"/users/{seeker_id}", json={"is_active": False}, headers=headers)
    assert response.status_code == 200
    assert response.json()["is_active"] is False

@pytest.mark.asyncio
async def test_credentials(client):
    """Test saving portal credentials."""
    token = await test_auth_flow(client)
    headers = {"Authorization": f"Bearer {token}"}
    
    # First create a seeker
    seeker_email = f"seeker_{uuid.uuid4().hex[:6]}@example.com"
    seeker_payload = {
        "email": seeker_email,
        "password": "Password123!",
        "full_name": "Job Seeker",
        "role": "job_seeker"
    }
    resp = await client.post("/users", json=seeker_payload, headers=headers)
    seeker_id = resp.json()["id"]
    
    # Save credentials
    cred_payload = {
        "user_id": seeker_id,
        "portal": "indeed",
        "username": "indeed_user",
        "password": "indeed_password"
    }
    response = await client.post("/credentials", json=cred_payload, headers=headers)
    assert response.status_code == 201
    assert response.json()["portal"] == "indeed"

@pytest.mark.asyncio
async def test_job_preferences(client):
    """Test job preference management."""
    token = await test_auth_flow(client)
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create seeker
    seeker_email = f"seeker_{uuid.uuid4().hex[:6]}@example.com"
    resp = await client.post("/users", json={
        "email": seeker_email, 
        "password": "Password123!", 
        "full_name": "Job Seeker", 
        "role": "job_seeker"
    }, headers=headers)
    assert resp.status_code == 201
    seeker_id = resp.json()["id"]
    
    # Save preferences
    pref_payload = {
        "user_id": seeker_id,
        "keywords": ["Python", "FastAPI"],
        "location": "Remote",
        "job_type": "full_time",
        "portals": ["indeed", "dice"]
    }
    response = await client.post("/preferences", json=pref_payload, headers=headers)
    assert response.status_code == 201
    assert "Python" in response.json()["keywords"]

@pytest.mark.asyncio
async def test_applications_stats(client):
    """Test applications stats endpoint."""
    token = await test_auth_flow(client)
    headers = {"Authorization": f"Bearer {token}"}
    
    response = await client.get("/applications/stats", headers=headers)
    assert response.status_code == 200
    assert "total_all_time" in response.json()
