from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, images, processing, results, satellite
from app.core.config import get_settings
from app.core.database import Base, engine

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # MVP schema init: create_all() rather than Alembic migrations. Fine
    # while the schema is still settling; revisit once it needs to evolve
    # without dropping data.
    import app.models  # noqa: F401 — registers all models on Base.metadata

    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="SRM Platform API",
    description=(
        "Backend for the Deep Learning Based Super Resolution Mapping platform. "
        "Processing is currently mocked — see app/services/processors."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"
app.include_router(health.router, prefix=API_PREFIX)
app.include_router(images.router, prefix=API_PREFIX)
app.include_router(processing.router, prefix=API_PREFIX)
app.include_router(results.router, prefix=API_PREFIX)
app.include_router(satellite.router, prefix=API_PREFIX)


@app.get("/")
def root() -> dict:
    return {"service": "SRM Platform API", "docs": "/docs"}
