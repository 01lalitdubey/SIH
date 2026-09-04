# SRM Platform — Backend

FastAPI backend for the Deep Learning Based Super Resolution Mapping
platform. This phase (Phase 3) builds the backend foundation only:
database, image upload, and a **mocked** processing pipeline. No AI, no
satellite APIs — see [Mocked vs Real](#mocked-vs-real) below.

## Stack

Python · FastAPI · SQLAlchemy · PostgreSQL · Pydantic · Uvicorn

## Project layout

```
backend/
├── app/
│   ├── main.py                  FastAPI app, CORS, router registration
│   ├── api/                     Route handlers (thin — no business logic)
│   ├── models/                  SQLAlchemy ORM models
│   ├── schemas/                 Pydantic request/response models
│   ├── services/                Business logic
│   │   └── processors/          Processor interface + MockProcessor
│   ├── core/                    Settings, DB session
│   └── utils/                   File/filename helpers
├── tests/                       Pytest suite (TestClient, SQLite-backed)
├── uploads/                     Uploaded imagery (gitignored contents)
├── outputs/                     Mock processing outputs (gitignored contents)
├── docker-compose.yml           Local Postgres for development
├── requirements.txt
└── .env.example
```

## Setup

### 1. Virtual environment

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. PostgreSQL

This project ships a `docker-compose.yml` that runs a dedicated Postgres
container on **port 5433** (not 5432) so it never collides with a
system-wide PostgreSQL install:

```bash
docker compose up -d
```

If you'd rather use your own PostgreSQL server, just create a database and
point `DATABASE_URL` at it (see below) — nothing in the app assumes Docker.

### 3. Environment configuration

```bash
cp .env.example .env
```

Defaults in `.env.example` already match `docker-compose.yml`. Edit
`DATABASE_URL` if you're pointing at a different Postgres instance.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLAlchemy connection string |
| `UPLOAD_DIR` | Where uploaded imagery is stored (relative to `backend/`) |
| `OUTPUT_DIR` | Where mock processing outputs are stored |
| `CORS_ORIGINS` | Comma-separated list of allowed frontend origins |
| `ENV` | `development` / `production` (informational) |

### 4. Database initialization

Tables are created automatically on startup (`Base.metadata.create_all`) —
no separate migration step is needed for this phase. Alembic-based
migrations can be introduced later once the schema needs to evolve without
losing data.

### 5. Run the server

```bash
uvicorn app.main:app --reload --port 8000
```

- API base: `http://localhost:8000/api/v1`
- Interactive docs (Swagger): `http://localhost:8000/docs`
- OpenAPI schema: `http://localhost:8000/openapi.json`

## API summary

All endpoints are prefixed with `/api/v1`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Service + DB connectivity check |
| POST | `/images/upload` | Upload an image (multipart) |
| GET | `/images` | List uploaded images |
| GET | `/images/{image_id}` | Get one image's metadata |
| POST | `/process` | Create a processing job (mocked pipeline) |
| GET | `/process/{job_id}` | Poll job status/progress/stage |
| GET | `/results/{job_id}` | Get a completed job's mock metrics |

Full request/response schemas are in Swagger at `/docs`.

## Mocked vs Real

| Area | This phase | Future |
|---|---|---|
| Processing pipeline | `MockProcessor` — timed stage transitions, real Pillow resize if an input image exists, randomized-but-plausible metrics | Real PyTorch super-resolution model (Phase 6) |
| Metrics (PSNR/SSIM/LPIPS) | Randomized within plausible ranges, always flagged `is_mock: true` | Computed against ground truth (Phase 7) |
| Satellite/AOI data | AOI bounds are stored as submitted by the frontend map; no real scene is fetched | Copernicus Data Space / Sentinel-2 (Phase 5) |
| Job execution | FastAPI `BackgroundTasks` (in-process) | Celery/Redis queue, once real inference needs a GPU worker (Phase 6) |
| Auth | None | Not yet scoped |

The mock pipeline is isolated behind `BaseProcessor` (`app/services/processors/base.py`)
so it can be swapped for a real processor later without touching the API layer:

```
ProcessingService
      |
      v
Processor Interface (BaseProcessor)
      |
      v
MockProcessor              <- current
RealSatelliteProcessor     <- future
      |
      v
SuperResolutionModel       <- future
```

## Failure simulation

`POST /process` accepts an optional `simulate_failure: true` flag. When set,
`MockProcessor` runs normally through `preprocessing` and
`feature_extraction`, then fails during `super_resolution` with a clear
`error_message` — mirroring the frontend's existing "Simulate failure
(demo)" button so that flow has a real backend path to eventually call.

## Testing

```bash
pytest
```

The test suite (`tests/`) uses FastAPI's `TestClient` against an in-memory
SQLite database (via a dependency override), so it doesn't require Postgres
or Docker to run. See [Manual test log](#manual-test-log) below for the
live Postgres verification performed during development.

## Manual test log

The following were run against a live Postgres (Docker) instance during
development of this phase, via `curl`:

1. `GET /health` → `200`, `database: connected`
2. `POST /images/upload` (valid JPEG) → `201`, correct width/height extracted
3. `POST /images/upload` (`.txt` file) → `415`; (no file) → `422`
4. `GET /images` → `200`, list includes uploaded images
5. `GET /images/{id}` → `200`; unknown id → `404`
6. `POST /process` (with `image_id`) → `201`, `status: queued`
7. `GET /process/{job_id}` polled every second → observed
   `processing → preprocessing → feature_extraction → super_resolution →
   post_processing → completed`, progress `0 → 20 → 40 → 60 → 80 → 100`
8. Job reached `completed` with `started_at`/`completed_at` populated
9. `POST /process` with `simulate_failure: true` → failed during
   `super_resolution` with a clear `error_message`; `GET /results/{job_id}`
   correctly returned `404` for the failed job
10. `GET /results/{job_id}` on a completed job → real Pillow-resized output
    file confirmed on disk, `output_width`/`output_height` matched
    `input × scale_factor`, metrics present and `is_mock: true`
11. AOI-only job (no `image_id`) → completed with mock metrics, `output_path: null`
