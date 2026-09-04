import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PILImage
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import database as db_module
from app.core.database import Base, get_db
from app.main import app

# In-memory SQLite for the test suite — no Postgres/Docker required. The
# GUID column type (app/core/types.py) is what makes the same models work
# against both dialects.
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

# MockProcessor runs in a background task and deliberately opens its own
# session via app.core.database.SessionLocal (see mock_processor.py) rather
# than reusing a request-scoped one. Point that at the same test database so
# background-task writes are visible to the test's assertions.
db_module.SessionLocal = TestingSessionLocal


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_image_bytes() -> bytes:
    buf = io.BytesIO()
    PILImage.new("RGB", (200, 100), color=(10, 120, 200)).save(buf, format="JPEG")
    return buf.getvalue()
