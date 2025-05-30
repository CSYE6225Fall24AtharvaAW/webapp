import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.main import app  # Import your FastAPI app
from app.database import get_db
from app.models.user import Base
from itsdangerous import URLSafeTimedSerializer
import os

@pytest.fixture
async def client(async_session: AsyncSession):
    """Create a test client for the FastAPI app."""
    async def override_get_db():
        yield async_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.mark.asyncio
async def test_create_user(client):
    response = await client.post("/v2/users/", json={
        "email": "test@example.com",
        "password": "testpassword",
        "first_name": "Test",
        "last_name": "User"
    })
    # Generate the token for email verification
    serializer = URLSafeTimedSerializer(os.getenv("SECRET_KEY"))
    token = serializer.dumps({"email": "test@example.com"}, salt="email-verification-salt")
    verify = await client.get(f"/v2/users/verify?user=test@example.com&token={token}")\
    
    assert response.status_code == 201
    assert response.json()["email"] == "test@example.com"
    assert verify.status_code == 200
    assert verify.json()["message"] == "Email successfully verified"

@pytest.mark.asyncio
async def test_get_user(client):
    response = await client.get("/v2/users/1", auth=("test@example.com", "testpassword"))
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"

@pytest.mark.asyncio
async def test_update_user(client):
    response = await client.put("/v2/users/1", json={
        "first_name": "Updated",
        "last_name": "User",
        "password": "newpassword"
    }, auth=("test@example.com", "testpassword"))
    
    assert response.status_code == 200
    assert response.json()["first_name"] == "Updated"

@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/v2/healthz")
    assert response.status_code == 200
