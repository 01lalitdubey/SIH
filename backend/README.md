# SRM Platform — Backend

FastAPI backend for the Deep Learning Based Super Resolution Mapping
platform. Phase 3 built the backend foundation (database, image upload, a
**mocked** processing pipeline); Phase 4 connects the existing frontend to
it (real uploads, real job polling, file-serving endpoints for the
before/after slider). No AI, no satellite APIs yet — see
[Mocked vs Real](#mocked-vs-real) below.

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

> **SQLite fallback:** if Postgres/Docker genuinely isn't available, you can
> point `DATABASE_URL` at `sqlite:///./dev.db` instead. This works because
> of the cross-dialect `GUID` column type (`app/core/types.py`) — the same
> models, same code, no changes needed. Treat this as a stopgap for local
> dev only, not a replacement for Postgres in the stated architecture.

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
| GET | `/images/{image_id}/file` | Serve the original image bytes (for `<img src>`) |
| POST | `/process` | Create a processing job (mocked pipeline) |
| GET | `/process` | List processing jobs (newest first) |
| GET | `/process/{job_id}` | Poll job status/progress/stage |
| GET | `/results/{job_id}` | Get a completed job's mock metrics |
| GET | `/results/{job_id}/file` | Serve the mock output image bytes |

The `/file` endpoints exist so the frontend never has to consume a raw
filesystem path directly — they look up the file by DB-verified id and
stream it via `FileResponse`, so a client can't request an arbitrary path
off disk.

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

## Phase 4 integration notes

Two additions exist specifically to support the frontend:

- `GET /process` (list) — the Dashboard needs job history; there was no
  "list all jobs" endpoint before this phase.
- `GET /images/{id}/file` and `GET /results/{job_id}/file` — the before/
  after slider needs browser-loadable image URLs; the JSON responses only
  ever contained server-side filesystem paths, which a browser can't load
  directly.

Full browser-to-database-to-browser verification (upload, AOI job, live
stage polling, completion, failure demo, invalid upload, nonexistent job,
backend-unavailable) was run against this backend from the frontend — see
`frontend/README.md` (Phase 4 section) for that test log.
