import pytest
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.models.user import Base  
import os

TEST_DATABASE_URL = os.getenv("DATABASE_URL")

@pytest.fixture(scope="session")
def event_loop():
    """Create a new event loop for each test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def test_db():
    """Create the test database and tables before each test function."""
    # Create the test database engine
    engine = create_async_engine(TEST_DATABASE_URL, echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # Create tables
    yield engine  # Provide the engine to tests

@pytest.fixture(scope="function")
async def async_session(test_db):
    """Provide an async session for the tests."""
    async_session_factory = sessionmaker(test_db, expire_on_commit=False, class_=AsyncSession)
    async with async_session_factory() as session:
        yield session  # Provide session to tests
