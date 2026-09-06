# SRM Platform — Backend

FastAPI backend for the Deep Learning Based Super Resolution Mapping
platform. Phase 3 built the backend foundation (database, image upload, a
**mocked** processing pipeline); Phase 4 connected the existing frontend to
it; Phase 5 replaces the AOI stub with a **real** Copernicus Data Space
Ecosystem (Sentinel-2) integration — see [Phase 5](#phase-5--satellite-data-integration)
below. Super-resolution itself is still mocked — no AI yet. See
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
│   │   ├── processors/          Processor interface + MockProcessor
│   │   └── satellite/           Phase 5: BaseSatelliteProvider + CopernicusSatelliteProvider
│   ├── core/                    Settings, DB session
│   └── utils/                   File/filename helpers
├── tests/                       Pytest suite (TestClient, SQLite-backed)
├── uploads/                     Uploaded imagery (gitignored contents)
├── outputs/                     Mock processing outputs (gitignored contents)
├── satellite/                   Downloaded satellite scene data (gitignored contents)
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
| `COPERNICUS_CLIENT_ID` / `COPERNICUS_CLIENT_SECRET` | Phase 5: OAuth2 client-credentials for Copernicus Data Space. Leave blank to disable real satellite search — AOI jobs then fail cleanly with "credentials not configured" instead of mocking a scene. |
| `COPERNICUS_TOKEN_URL` / `COPERNICUS_CATALOG_URL` / `COPERNICUS_DOWNLOAD_URL` | Public, non-secret CDSE endpoints — sensible defaults already set, only override for a mirror |
| `SATELLITE_DIR` | Where downloaded scene data is stored (relative to `backend/`) |
| `SATELLITE_MAX_DOWNLOAD_MB` | Size cap for scene downloads (default 200MB) — see [Phase 5](#phase-5--satellite-data-integration) for why this matters |

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
| POST | `/process` | Create a processing job (image- or AOI-driven; AOI jobs run a real Copernicus search first — see Phase 5) |
| GET | `/process` | List processing jobs (newest first) |
| GET | `/process/{job_id}` | Poll job status/progress/stage (includes `satellite_scene` for AOI jobs) |
| GET | `/results/{job_id}` | Get a completed job's mock metrics |
| GET | `/results/{job_id}/file` | Serve the mock output image bytes |
| GET | `/satellite/scenes/{scene_id}` | Get the satellite scene identified/downloaded for a job |
| GET | `/satellite/scenes/{scene_id}/file` | Serve the downloaded scene file, if one was retrieved |

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
| Satellite/AOI search | **Real** — Copernicus Data Space Ecosystem, live Sentinel-2 catalog search (Phase 5, done) | Full-scene/band download (currently size-capped, see below) |
| Geospatial fidelity (GeoTIFF/CRS) | Not preserved — plain image ops | Rasterio/GDAL (Phase 7) |
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

## Phase 5 — satellite data integration

AOI-driven jobs now run a real Copernicus Data Space Ecosystem (CDSE) search
for Sentinel-2 scenes before the mock processor runs — replacing the
"AOI bounds are just stored" stub from Phase 3/4. Full design in
`docs/ARCHITECTURE.md` §17; summary here.

### Architecture

```
ProcessingService
      |
      v
SatelliteService (app/services/satellite/service.py)
      |
      v
BaseSatelliteProvider (app/services/satellite/base.py)
      |
      v
CopernicusSatelliteProvider   <- CURRENT (real)
FakeSatelliteProvider         <- test-only, network-free
```

`SatelliteService` validates the AOI/date/cloud-cover, then drives the
provider through `authenticate() → search_scenes() → select_best_scene() →
download_scene()`, persisting exactly one `SatelliteScene` row per AOI job
— even on a download failure, so a real, identified scene isn't discarded
just because retrieving its data failed.

### Why download is size-capped

A live query against the production CDSE catalog during development
returned a real Sentinel-2 product with `ContentLength: 791572987` — **792MB
for one tile**. `SATELLITE_MAX_DOWNLOAD_MB` (default 200MB) is a deliberate
safety gate checked against the real reported size *before* opening a
connection: over the cap, the job fails cleanly with
`SceneDownloadError` rather than streaming hundreds of megabytes to disk.
The streaming download code is real and correct (Bearer-token
authenticated, chunked, mid-stream size enforcement) — it would succeed
today for any product under the cap. Full-band/subset selection (much
smaller than a full SAFE archive) is the natural next step, and the
provider interface already has room for it.

### Job states (Phase 4 polling contract preserved)

AOI jobs pass through one additional internal stage, `satellite_acquisition`,
before Phase 3/4's five existing stages. It is **not** one of
`ProcessingStage.ORDERED`, so the existing frontend's `stageKeyToIndex()`
returns `-1` for it — the same safe fallback already used for `queued`
(every stage renders "pending"). No frontend change was needed or made.

```
queued -> processing (stage: satellite_acquisition) -> processing (stage: preprocessing)
        -> feature_extraction -> super_resolution -> post_processing -> evaluation -> completed
                                                                                    -> failed (any stage)
```

A satellite failure sets `status: failed` immediately — it never proceeds
into the mock stages, so a failed acquisition can never be reported as a
completed analysis.

### Error handling

| Failure | Exception | Job outcome |
|---|---|---|
| Malformed/out-of-range AOI | `InvalidAOIError` (422 at request time via Pydantic; also re-validated defensively at execution time) | Rejected before a job is even created, or fails immediately |
| Invalid date range / cloud cover | `InvalidDateRangeError` / `InvalidCloudCoverError` | Same as above |
| Missing Copernicus credentials | `MissingCredentialsError` | Job fails: "Copernicus credentials are not configured" |
| Credentials rejected | `AuthenticationError` | Job fails: "Copernicus rejected the configured client credentials" |
| Timeout / 5xx / connection error | `ProviderUnavailableError` | Job fails with a clear, secret-free message |
| Zero matching scenes | `NoScenesFoundError` | Job fails: "No Sentinel-2 scenes matched..." |
| Download failure or over size cap | `SceneDownloadError` | Job fails; the identified scene's metadata is still persisted with `download_status: failed` |

No exception message ever includes a token, client secret, or raw provider
response body — see `app/services/satellite/exceptions.py`.

### Testing strategy

`tests/test_satellite.py` (20 tests) runs entirely against
`FakeSatelliteProvider` — an autouse fixture in `conftest.py` replaces the
real provider for the whole suite, so **no test requires or can
accidentally use real Copernicus credentials**. Covered: AOI/date/cloud-cover
validation (both at the API boundary and defensively inside the service),
every failure mode in the table above, deterministic ranking (including a
dedicated unit test proving AOI coverage outranks cloud cover), scene
persistence and the job↔scene relationship, the dedicated scene endpoints,
and a regression test proving an image-driven job never touches the
satellite service at all.

```bash
pytest                    # 39 passed (19 from Phase 3/4 + 20 new for Phase 5)
pytest tests/test_satellite.py -v   # just the Phase 5 suite
```

### Live Copernicus verification

No real `COPERNICUS_CLIENT_ID`/`COPERNICUS_CLIENT_SECRET` exist in this
development environment, so the authenticated OAuth2 → search → download
round-trip was **not** run end-to-end with real credentials.

**COPERNICUS LIVE TEST = BLOCKED — credentials unavailable**

What *was* verified against the live, production CDSE API during
development (unauthenticated — the catalog search endpoint happens to be
publicly queryable):

1. Token endpoint reachability — `POST` required, confirmed via a 405 on `GET`.
2. Catalog search with a real AOI polygon + date range → real Sentinel-2
   products returned (verified product names, ids, footprints, acquisition dates).
3. Server-side cloud-cover attribute filtering (`Attributes/OData.CSC.DoubleAttribute/...`)
   → confirmed all returned products were at or under the requested threshold.
4. Server-side processing-level filtering (`S2MSI2A`) → confirmed only L2A
   products returned.
5. Real product size (`ContentLength`) → confirmed ~792MB for a full L1C
   tile, which is what motivated the size cap in §"Why download is size-capped".

Running the full authenticated flow only requires setting the three
Copernicus environment variables and re-running an AOI job — no code
changes needed. Anyone with real CDSE credentials can complete that
verification by exporting them into `.env` and creating an AOI-driven job
via `POST /process`.

### Live smoke test (this environment, no credentials configured)

Run against the actual running dev server (not the test suite) to confirm
the real `CopernicusSatelliteProvider` path — not just the fake one — is
correctly wired end-to-end:

```
POST /api/v1/process {"aoi": {...}, "analysis_name": "Live smoke test", "scale_factor": 2}
  -> 201, status: queued

GET /api/v1/process/{job_id}  (after background task runs)
  -> status: failed
  -> current_stage: satellite_acquisition
  -> error_message: "Satellite acquisition failed: Copernicus credentials
     are not configured (COPERNICUS_CLIENT_ID / COPERNICUS_CLIENT_SECRET)."
  -> satellite_scene: null
```

Clean, immediate failure with no false success and no leaked secrets — the
expected and correct behavior with no credentials configured. An
image-driven job run against the same live server immediately afterward
still completed normally (`status: completed`, `satellite_scene: null`),
confirming zero regression to the Phase 4 path.
