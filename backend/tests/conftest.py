"""Pytest fixtures for backend tests with isolated test database and seeded accounts."""

import uuid
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.config import Settings
from app.core.security import create_access_token
from app.db.seed import seed_database
from app.main import create_app
from app.models.base import Base

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Fixture returning settings configured for test environment."""
    return Settings(
        ENVIRONMENT="test",
        DEBUG=True,
        SECRET_KEY="test-secret-key-for-unit-testing-at-least-32-chars-long",
        LOG_LEVEL="DEBUG",
        DATABASE_URL=TEST_DATABASE_URL,
        LOCAL_STORAGE_DIR="backend/data/test_uploads",
    )


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Create all database tables fresh before each test and tear down after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated async database session."""
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def seeded_db(db_session: AsyncSession) -> dict:
    """Seed the test database with standard synthetic departments, users, and documents."""
    return await seed_database(db_session)


@pytest.fixture
def app(test_settings: Settings):
    """FastAPI app instance with get_db overridden to use test database."""
    app_instance = create_app(test_settings)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with TestingSessionLocal() as session:
            yield session

    app_instance.dependency_overrides[get_db] = override_get_db
    return app_instance


@pytest.fixture
def client(app) -> TestClient:
    """FastAPI TestClient with overridden test database."""
    return TestClient(app)


def get_auth_header(user_id: uuid.UUID) -> dict[str, str]:
    """Helper to generate Authorization header for a given user ID."""
    token = create_access_token(user_id)
    return {"Authorization": f"Bearer {token}"}
