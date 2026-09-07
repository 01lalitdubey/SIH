# SRM Platform — Architecture Blueprint (Phase 0)

Status: **proposal, pending approval**. No application code has been written from this
document yet. This refines [PLAN.md](../PLAN.md) into an implementable blueprint for
Phases 1–4 (frontend, backend, integration) with processing explicitly mocked, and marks
where Phases 5–7 (satellite, AI, geospatial) plug in later.

Legend: **[MVP]** = build now, real. **[MOCK]** = build now, fake, clearly labeled in code.
**[FUTURE]** = design for, do not build yet.

---

## 1. Overall System Architecture

```
┌────────────┐        REST/JSON         ┌──────────────┐        SQL        ┌────────────┐
│  Frontend   │ ───────────────────────▶ │   Backend     │ ─────────────────▶ │ PostgreSQL │
│ React+Vite  │ ◀─────────────────────── │   FastAPI     │ ◀───────────────── │            │
└────────────┘                           └──────┬───────┘                    └────────────┘
                                                 │
                                                 ▼
                                          ┌──────────────┐
                                          │ Local storage │  [MVP: disk]
                                          │ (uploads/     │  [FUTURE: S3/MinIO]
                                          │  results)     │
                                          └──────────────┘
                                                 │
                                    [MOCK now]   ▼   [FUTURE: real]
                                          ┌──────────────────┐
                                          │ Processing service │
                                          │  - mock SR today   │
                                          │  - PyTorch SR later │
                                          │  - Sentinel-2 fetch │
                                          │    later            │
                                          └──────────────────┘
```

Frontend and backend are fully decoupled, talking only over a documented REST API. The
processing step is an internal backend service boundary — swapping the mock for the real
AI/satellite pipeline later must not require frontend or API contract changes.

---

## 2. Frontend Architecture

- **React + Vite**, functional components + hooks only.
- **React Router** for the 4 MVP pages (+ routes as they grow).
- **State**: local component state + React Context for cross-cutting state (current job,
  theme). No Redux — not justified at this scale.
- **Data fetching**: a thin `api/` client wrapping `fetch` against the backend base URL
  (`VITE_API_BASE_URL`). (TanStack Query is worth adding once real polling/caching needs
  appear in Phase 4 — not installed yet, flagged for that phase, not decided now.)
- **Styling**: Tailwind CSS, dark theme by default, design tokens (colors/spacing/type)
  centralized in `tailwind.config.js`.
- **Animation**: Framer Motion for page transitions and the "scanning / processing"
  motifs described in the brief.
- **Maps**: React Leaflet for AOI selection/visualization.
- **Charts**: Recharts for evaluation metrics (PSNR/SSIM/LPIPS) — used from Phase 7
  onward, component built earlier with mock data.

## 3. Backend Architecture

- **FastAPI**, structured by domain, not by technical layer alone:
  - `api/` — routers (thin, request/response only)
  - `services/` — business logic (upload handling, job orchestration, mock processing)
  - `models/` — SQLAlchemy ORM models
  - `schemas/` — Pydantic request/response models
  - `core/` — settings (via `pydantic-settings`), DB session, app config
- **Job execution [MVP/MOCK]**: FastAPI `BackgroundTasks` runs the mock processing step
  asynchronously after job creation, updating job status in the DB as it goes
  (`pending → processing → completed`). No queue/broker needed at this scale.
- **Job execution [FUTURE]**: when real AI inference is added (Phase 6), replace
  `BackgroundTasks` with a real task queue (Celery/RQ + Redis) so long GPU jobs don't
  block the API process. This is an internal swap behind the same `services/jobs.py`
  interface.
- **Migrations**: Alembic from the start, so schema changes are tracked even in MVP.

## 4. API Architecture

- REST, JSON, prefixed `/api/v1/...`.
- Resource-oriented: `images`, `aoi`, `jobs`, `jobs/{id}/result`.
- Consistent error envelope: `{"detail": "message"}` (FastAPI default) — kept uniform,
  no custom wrapper unless a real need appears.
- File responses (uploaded images, result images) served via dedicated
  `GET .../file` endpoints returning `FileResponse`, not embedded as base64 in JSON.
- CORS restricted to the frontend origin via `CORS_ORIGINS` env var.

## 5. Database Schema (MVP)

PostgreSQL, no PostGIS extension yet — AOI geometry stored as GeoJSON in a `JSONB`
column for MVP simplicity. Revisit PostGIS in Phase 7 if spatial queries are needed.

```
images
  id            UUID PK
  filename      TEXT
  storage_path  TEXT
  content_type  TEXT
  width         INT
  height        INT
  size_bytes    INT
  uploaded_at   TIMESTAMPTZ

aoi
  id            UUID PK
  name          TEXT
  geometry      JSONB        -- GeoJSON polygon
  source        TEXT         -- 'manual' | 'mock_search' [FUTURE: 'copernicus']
  created_at    TIMESTAMPTZ

jobs
  id            UUID PK
  image_id      UUID FK -> images.id (nullable if AOI-driven)
  aoi_id        UUID FK -> aoi.id (nullable if image-upload-driven)
  job_type      TEXT         -- 'mock_sr' [FUTURE: 'sr_v1', ...]
  status        TEXT         -- 'pending' | 'processing' | 'completed' | 'failed'
  progress      INT          -- 0-100
  error_message TEXT NULL
  created_at    TIMESTAMPTZ
  updated_at    TIMESTAMPTZ

results
  id             UUID PK
  job_id         UUID FK -> jobs.id
  result_path    TEXT
  metrics        JSONB NULL   -- {psnr, ssim, lpips} — NULL in MVP mock
  is_mock        BOOLEAN      -- true until Phase 6 lands
  created_at     TIMESTAMPTZ
```

`users` table intentionally **not** added in MVP — see §10 Authentication.

## 6. Image-Processing Pipeline

- **[MOCK now]**: on job creation, the backend takes the uploaded image and produces a
  "result" via a simple, clearly-labeled placeholder transform (e.g. PIL bicubic resize
  up 2x, or an even simpler copy). Code path: `services/processing/mock_sr.py`, explicitly
  named and commented `MOCK/TEMPORARY`. Purpose is only to exercise the full
  upload → job → result → display flow.
- **[FUTURE]**: `services/processing/` gains a real pipeline: Rasterio-based
  reprojection/tiling/normalization → PyTorch model inference → re-embed georeferencing →
  GeoTIFF write. Same service interface (`run(job) -> result`), so routers/DB/frontend
  don't change when the real implementation lands.

## 7. Satellite-Data Pipeline

- **[REAL, Phase 5]**: AOI-driven jobs run a real Copernicus Data Space Ecosystem (CDSE)
  search before the mock processor ever runs — no hardcoded scene list. See
  **§17 Phase 5 — Satellite Data Integration** below for the full design; this
  section is kept for historical continuity with Phases 0-4.
- Superseded: there never was an `/api/v1/aoi/search` endpoint — Phase 5 wires
  satellite acquisition directly into `POST /api/v1/process` instead (an AOI-driven
  job *is* the search), which needed no new upload-style endpoint.

## 8. AI Pipeline

- **[MOCK now]**: no model, no PyTorch dependency installed yet. The "SR" step is the
  placeholder transform from §6.
- **[FUTURE, Phase 6]**: PyTorch inference service, model artifact stored under a
  `MODEL_PATH`, architecture selection deferred until then (per PLAN.md — not decided).

## 9. Storage Architecture

- **[MVP]**: local filesystem, `backend/storage/uploads/` and `backend/storage/results/`,
  paths recorded in DB (never re-derive paths from IDs by convention — store the actual
  path, so storage backend can change later without a migration of logic).
- **[FUTURE]**: swap to S3-compatible object storage (e.g. MinIO self-hosted or AWS S3)
  behind a small storage-adapter interface (`services/storage.py`) — same reasoning as
  the processing swap: routers never touch the filesystem directly.

## 10. Authentication Strategy

Recommendation for a hackathon-scoped MVP: **no authentication in Phase 1–4**; the app
runs as a single implicit demo user. This is called out explicitly rather than silently
assumed, because it affects schema and API design:

- DB tables avoid hardcoding a `user_id` that doesn't exist yet, but are structured so a
  `users` table + `owner_id` FK could be added additively later without breaking existing
  tables (no premature FK now — YAGNI).
- **[FUTURE]**: if judges/demo requirements need login, add FastAPI + JWT
  (OAuth2 password flow), a `users` table, and `owner_id` on `jobs`/`aoi`. This is a
  contained addition, not a redesign.

If you'd rather have basic auth from the start (e.g. for a multi-team demo), flag that
now — it's cheap to add in Phase 3 but should be decided before backend scaffolding.

## 11. Frontend Page Structure (MVP)

| Page | Route | Purpose |
|---|---|---|
| Landing | `/` | Platform intro, value proposition, CTA into the app |
| Dashboard | `/dashboard` | List of past jobs/analyses with status, quick stats |
| Process / New Analysis | `/process` | Upload image or select AOI, configure & submit a job |
| Results | `/results/:jobId` | Before/after viewer, metrics panel (mocked for now), download |

## 12. Component Structure

```
components/
  common/       Navbar, Footer, Button, Card, Modal, Spinner, Toast
  layout/       AppShell, PageHeader
  process/      FileUploader, AOISelector, JobConfigForm
  map/          MapView (Leaflet wrapper), AOIDrawTool
  results/      ImageCompareSlider, MetricsPanel, DownloadButton
  dashboard/    JobList, JobCard, JobStatusBadge
  animation/    ScanningOverlay, ProcessingIndicator   (Framer Motion motifs)
```

Feature-first grouping (not "atoms/molecules"), matching page structure above so
ownership is obvious.

## 13. Folder Structure (target, created incrementally per phase)

```
SIH/
├── PLAN.md
├── docs/
│   └── ARCHITECTURE.md
├── frontend/
│   ├── src/
│   │   ├── pages/           Landing.tsx, Dashboard.tsx, Process.tsx, Results.tsx
│   │   ├── components/      (see §12)
│   │   ├── api/             client.ts, jobs.ts, images.ts, aoi.ts
│   │   ├── context/
│   │   ├── hooks/
│   │   ├── styles/
│   │   └── main.tsx / App.tsx
│   ├── public/
│   ├── index.html
│   ├── tailwind.config.js
│   ├── vite.config.ts
│   └── package.json
├── backend/
│   ├── app/
│   │   ├── api/v1/          images.py, aoi.py, jobs.py
│   │   ├── services/        processing/mock_sr.py, storage.py, jobs.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── core/            config.py, db.py
│   │   └── main.py
│   ├── storage/              uploads/, results/   (gitignored)
│   ├── alembic/
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
└── .gitignore
```

## 14. Development Dependencies

**Frontend (Phase 1):** `react`, `react-dom`, `react-router-dom`, `vite`, `tailwindcss`,
`framer-motion`, `react-leaflet`, `leaflet`, `lucide-react`, `recharts`, `eslint`,
`prettier`.

**Backend (Phase 3):** `fastapi`, `uvicorn`, `sqlalchemy`, `alembic`, `pydantic`,
`pydantic-settings`, `python-dotenv`, `psycopg2-binary` (or `asyncpg` if going async DB),
`python-multipart` (file uploads), `Pillow` (mock image transform), `pytest`,
`httpx` (test client).

**[FUTURE, not installed now]:** `rasterio`, `gdal`, `geopandas` (Phase 7),
`torch`/`torchvision` (Phase 6), `celery` + `redis` (Phase 6, if queue needed),
`boto3` or `minio` client (storage upgrade).

## 15. Environment Variables

**Backend (`backend/.env`):**
```
DATABASE_URL=postgresql://user:password@localhost:5432/srm_db
CORS_ORIGINS=http://localhost:5173
STORAGE_DIR=./storage
ENV=development
# FUTURE (Phase 5):
COPERNICUS_CLIENT_ID=
COPERNICUS_CLIENT_SECRET=
# FUTURE (Phase 6):
MODEL_PATH=
# FUTURE (only if auth is added):
SECRET_KEY=
JWT_ALGORITHM=HS256
```

**Frontend (`frontend/.env`):**
```
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

Both get a committed `.env.example`; real `.env` files are gitignored.

## 16. Future Deployment Architecture

```
                 ┌──────────────┐
                 │   Frontend    │  static build → Vercel/Netlify
                 │ (React build) │  or containerized behind nginx
                 └──────┬───────┘
                        │ HTTPS
                 ┌──────▼───────┐
                 │ Backend API   │  Dockerized FastAPI, Render/Railway/AWS
                 │ (Uvicorn)     │
                 └──┬────────┬──┘
                    │        │
           ┌────────▼──┐  ┌──▼─────────────┐
           │ PostgreSQL │  │ Object storage │  S3/MinIO for images + GeoTIFFs
           │ (managed)  │  └────────────────┘
           └────────────┘
                    │
           ┌────────▼─────────┐
           │ GPU inference     │  separate service/queue worker,
           │ worker (Phase 6+) │  only added once AI phase begins
           └───────────────────┘
```

CI/CD via GitHub Actions (lint/test on PR); not set up until Phase 10.

---

## Initial Backend API List (MVP, mocked processing)

| Method | Path | Purpose | MVP behavior |
|---|---|---|---|
| POST | `/api/v1/images` | Upload an image | Real — stores file, creates `images` row |
| GET | `/api/v1/images/{id}` | Image metadata | Real |
| POST | `/api/v1/aoi/search` | Search AOI for satellite scenes | **MOCK** — hardcoded scene list |
| POST | `/api/v1/jobs` | Create processing job (from image or AOI) | Real job creation, **mocked** processing |
| GET | `/api/v1/jobs/{id}` | Job status/progress | Real |
| GET | `/api/v1/jobs/{id}/result` | Get result metadata + metrics | Real record, **mocked** metrics (null/placeholder) |
| GET | `/api/v1/jobs/{id}/result/file` | Download result image | Real file, **mock**-generated content |

## MVP vs Future — Summary

| Area | MVP (build now) | Future (later phase) |
|---|---|---|
| Processing | Mock transform, instant/fast | Real PyTorch SR (Phase 6) |
| Satellite data | **Real** Copernicus/Sentinel-2 search + selection (Phase 5, done) | Full-scene/band download (currently size-capped — see §17) |
| Geospatial fidelity | Not preserved (plain image ops) | Rasterio/GDAL, GeoTIFF, CRS-preserving (Phase 7) |
| Storage | Local disk | S3/MinIO object storage |
| Auth | None (single demo user) | JWT-based, if required |
| Job execution | FastAPI BackgroundTasks | Celery/Redis queue |
| Metrics (PSNR/SSIM/LPIPS) | Null/placeholder in schema | Computed for real (Phase 7) |

---

## 17. Phase 5 — Satellite Data Integration (done)

Status: **implemented and tested**. Replaces the never-built AOI-search stub described
in §7/§10 of this document's original (Phase 0) proposal with a real Copernicus Data
Space Ecosystem (CDSE) integration for Sentinel-2.

### 17.1 Where it sits in the pipeline

```
AOI (frontend, unchanged)
   |
   v
POST /api/v1/process  { aoi, [start_date, end_date, max_cloud_cover] }
   |
   v
processing_service._run_job_pipeline (background task)
   |
   +-- job.aoi_geometry is not null? -----------------------------+
   |                                                                |
   |  NO (image_id job)                                    YES (AOI job)
   |  |                                                             |
   |  v                                                             v
   |  MockProcessor.run()                          job.current_stage = "satellite_acquisition"
   |  (unchanged, Phase 3/4)                                        |
   |                                                                 v
   |                                                  SatelliteService.acquire_scene_for_job
   |                                                        |
   |                                              validate AOI / dates / cloud cover
   |                                                        |
   |                                              CopernicusSatelliteProvider.authenticate()
   |                                                        |
   |                                              CopernicusSatelliteProvider.search_scenes()
   |                                                        |
   |                                              BaseSatelliteProvider.select_best_scene()
   |                                                        |
   |                                              CopernicusSatelliteProvider.download_scene()
   |                                                        |
   |                                              persist SatelliteScene row, link to job
   |                                                        |
   |                                              failure at any step -> job.status = failed, STOP
   |                                                        |
   |                                              success -----+
   |                                                            |
   +------------------------------------------------------------+
                              |
                              v
                     MockProcessor.run()  (Phase 3/4, unchanged)
```

An image-driven job never enters the satellite branch at all — zero behavior change
for Phase 4's existing flow. An AOI-driven job's real scene search happens strictly
*before* the mock pipeline; if it fails, the job fails immediately and never reaches
(or fakes) the mock stages, so a failed satellite acquisition can never look like a
successful analysis.

### 17.2 Satellite service architecture

```
backend/app/services/satellite/
  base.py        BaseSatelliteProvider (ABC) + AOIPolygon/SearchParams/SceneCandidate/
                  DownloadResult dataclasses + the shared select_best_scene() ranking
  copernicus.py   CopernicusSatelliteProvider — the real implementation
  fake.py         FakeSatelliteProvider — deterministic, network-free, test-only
  storage.py      BaseSatelliteStorage (ABC) + LocalSatelliteStorage
  service.py      SatelliteService-equivalent module: validation + orchestration +
                  DB persistence; the only thing processing_service.py calls
  exceptions.py   SatelliteError and its subclasses (one per failure mode)
```

`processing_service.py` and every test depend only on `base.BaseSatelliteProvider` —
never on `copernicus.py` directly — so `fake.py` is a drop-in for tests, and a second
real provider would be a drop-in for production, with no change to `service.py`'s
orchestration logic.

### 17.3 Copernicus API integration (verified against the live API)

| Call | Endpoint | Verified how |
|---|---|---|
| Token (OAuth2 client-credentials) | `POST {COPERNICUS_TOKEN_URL}` | Endpoint reachability confirmed live (correctly rejects GET with 405); the authenticated exchange itself is untested — no real client credentials exist in this environment. |
| Catalog search | `GET {COPERNICUS_CATALOG_URL}/Products?$filter=...&$expand=Attributes` | **Executed live**, unauthenticated, during development: real Sentinel-2 products returned for a real AOI polygon + date range, with server-side cloud-cover and processing-level (`S2MSI2A`) filtering confirmed correct. |
| Download | `GET {COPERNICUS_DOWNLOAD_URL}/Products({id})/$value` (Bearer token) | Endpoint pattern per CDSE's documented OData download convention; code path is real (streamed, size-capped) but unauthenticated download was not attempted (would require real credentials and, per below, would mostly hit the size cap anyway). |

The catalog search being publicly queryable was a genuine discovery made while building this — it let real search/ranking logic be validated against live data even with zero credentials configured, which is why those parts of this phase carry higher confidence than the authenticated paths.

**The $filter clause actually sent** (AOI polygon intersection, a date window, and two
server-side attribute filters — cloud cover and processing level — all in one query):

```
Collection/Name eq 'SENTINEL-2' and
OData.CSC.Intersects(area=geography'SRID=4326;POLYGON((west south, west north, east north, east south, west south))') and
ContentDate/Start gt {start}T00:00:00.000Z and
ContentDate/Start lt {end}T00:00:00.000Z and
Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' and att/OData.CSC.DoubleAttribute/Value le {max_cloud_cover}) and
Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'processingLevel' and att/OData.CSC.StringAttribute/Value eq 'S2MSI2A')
```

L2A (surface reflectance, atmospherically corrected) is preferred over raw L1C —
the standard analysis-ready Sentinel-2 product for this kind of platform.

### 17.4 Why download is size-capped, not "not implemented"

A live query during development returned a real Sentinel-2 L1C product with
`ContentLength: 791572987` — **~792MB for one tile**. `SATELLITE_MAX_DOWNLOAD_MB`
(default 200MB) is a deliberate safety gate: `CopernicusSatelliteProvider.download_scene`
checks the real `ContentLength` from search results before ever opening a connection,
and refuses (`SceneDownloadError`, job fails cleanly) rather than streaming
hundreds of megabytes into a hackathon-scoped MVP. This is exactly what
`docs/ARCHITECTURE.md`'s original Phase 5 brief asked for ("do not blindly download
enormous datasets; identify the smallest practical retrieval"). The streaming download
code itself is real and correct — it would succeed today for any product under the cap
— and the architecture explicitly leaves room for a follow-up that requests individual
bands/subsets (much smaller) instead of the full SAFE archive, without changing the
provider interface.

### 17.5 AOI, dates, and cloud cover — request shape

The frontend is unchanged and still sends `aoi: {north, south, east, west}`. Two new
**optional** fields were added to `POST /api/v1/process`, additive and backward
compatible:

```json
{
  "aoi": {"north": 25.7, "south": 20.6, "east": 81.6, "west": 72.4},
  "analysis_name": "Coastal Delta — Sundarbans",
  "scale_factor": 4,
  "start_date": "2026-08-01",
  "end_date": "2026-09-01",
  "max_cloud_cover": 20
}
```

If `start_date`/`end_date`/`max_cloud_cover` are omitted (the existing frontend never
sends them), `SatelliteService` applies documented defaults: the last 30 days, and a
20% max cloud cover. The resolved values are stored alongside the AOI bounds in the
existing `aoi_geometry` JSON column (no new `ProcessingJob` columns needed) under a
nested `search` key.

### 17.6 Scene ranking (deterministic, documented, never random)

`BaseSatelliteProvider.select_best_scene` (shared by every provider, including the
fake one used in tests) ranks candidates by:

1. **AOI coverage** — bounding-box overlap ratio between the scene's footprint and the
   requested AOI (pure Python, no shapely/GDAL dependency — real polygon intersection
   is Phase 7 territory and isn't needed here since the search query already filters to
   intersecting scenes; this only affects tie-break order).
2. **Cloud cover**, ascending.
3. **Acquisition date distance from the requested `end_date`**, ascending.

### 17.7 Database change

One new table, additive only — no existing table was redesigned:

```
satellite_scenes
  id                     UUID PK
  processing_job_id      UUID FK -> processing_jobs.id, unique (one scene per job)
  provider               TEXT           -- 'copernicus'
  product_id             TEXT
  product_name           TEXT
  collection             TEXT           -- 'SENTINEL-2'
  platform               TEXT NULL      -- e.g. 'Sentinel-2C'
  instrument             TEXT NULL      -- 'MSI'
  acquisition_datetime   TIMESTAMPTZ NULL
  cloud_cover            FLOAT NULL
  footprint              JSONB NULL     -- real GeoJSON Polygon
  size_bytes             BIGINT NULL
  source_url             TEXT NULL
  download_status        TEXT           -- pending | downloading | completed | failed | skipped
  download_path          TEXT NULL
  download_error         TEXT NULL
  created_at             TIMESTAMPTZ
```

`ProcessingJob` gained one new relationship (`satellite_scene`), no new columns.
`Image -> ProcessingJob -> Result` is untouched; `ProcessingJob -> SatelliteScene` is a
parallel, optional one-to-one edge for AOI-driven jobs only.

### 17.8 Real vs. mocked, precisely

| Step | Status |
|---|---|
| AOI capture (frontend map) | Real (Phase 2/4, unchanged) |
| AOI validation (bounds, dates, cloud cover) | Real |
| Copernicus OAuth2 authentication | Real code; unverified live (no credentials available) |
| Sentinel-2 catalog search | Real, **verified live** against the production CDSE API |
| Scene ranking/selection | Real, deterministic |
| Scene metadata persistence | Real |
| Scene download | Real code, size-capped by design (see §17.4) |
| Super-resolution | **Mock** — MockProcessor, unchanged since Phase 3 |
| PSNR/SSIM/LPIPS | **Mock** — unchanged since Phase 3 |
| GeoTIFF / CRS preservation | Not yet — Phase 7 |

---

Phase 5 complete.

## 18. Phase 6 — AI Super Resolution (done)

Replaces `MockProcessor`'s fake resize with a real, trained PyTorch model behind the
same `BaseProcessor` interface — selectable via `PROCESSOR_MODE`, never a silent
fallback. Full test/experiment log in `backend/README.md`; summary here.

### 18.1 Dataset — SEN2VENuS v2.0 (real, verified live)

`tacofoundation/sen2venus` on Hugging Face — Sentinel-2 (10m) paired with same-day,
same-footprint VENuS reference imagery (5m), TACO-packaged. Verified for real,
during development, against the live dataset (not assumed):

- **124,123 real patch pairs**, 28 distinct regions, all natively `scale_factor: 2`.
- Each pair: LR = 128x128px @ 10m (10 Sentinel-2 bands), HR = 256x256px @ 5m
  (8 VENuS bands) — same UTM footprint, confirmed via matching geotransform origins.
  This is exactly the "10m -> 2x -> 5m" milestone from the original Phase 6 brief,
  confirmed from the data rather than assumed.
- The dataset's own `tortilla:data_split` column exists but — checked, not assumed —
  every one of the 124,123 rows is labeled `'train'`. There is no usable test split
  in the data itself, so `ai/datasets/sen2venus.py` implements its own **region-aware**
  split instead (an entire region goes to train/val/test, never split across them,
  since patches inside one region overlap and tile a shared area) — 20 regions train,
  4 val, 4 test, seeded and deterministic.
- Pixel values: uint16. Six real samples spanning six different regions (ALSACE, ARM,
  ESGISB-1, FR-LAM, KUDALIAR, SO1) showed ranges from ~0 to ~5700, consistent with the
  standard Sentinel-2 L2A "reflectance x 10000" convention — the normalization used
  (divide by 10000, clip to [0,1]).

**Why no rasterio/GDAL** (explicitly out of scope for Phase 6 per the brief): reading
this dataset's samples means resolving a `/vsisubfile/OFFSET_LEN,/vsicurl/URL`
reference into pixel data. Rather than pull in GDAL to resolve that virtual path,
`ai/datasets/sen2venus.py` does it directly: `tacoreader.v1`'s lightweight index
reader resolves the byte offset/length (reading only each remote file's small
footer/index, not its ~20GB body), a plain `httpx` Range GET fetches just those
bytes, and `tifffile` (a pure-numpy TIFF pixel decoder, no CRS/reprojection
capability) decodes the array. No GDAL, no rasterio, anywhere in Phase 6.

**RGB-only MVP**: bands `[0:3]` (Blue, Green, Red) of both LR and HR stacks are used
— this index alignment is exactly what the dataset's own official usage example
verifies (`rasterio.read([1,2,3])` on both sensors, commented "Blue, Green, Red").
The remaining 7 LR bands (including 20m SWIR B11/B12, which VENuS has no reference
for at all) are not used. Documented limitation, not a hidden assumption — extending
to more bands only requires changing `RGB_BAND_SLICE` and the model's `in_channels`.

### 18.2 Model — EDSR-lite

A configurable, lightweight EDSR-style residual CNN (`ai/models/edsr.py`): shallow
feature extraction -> N residual blocks (conv-ReLU-conv, residual-scaled) -> long skip
-> PixelShuffle learned upsampling (2x, or two cascaded 2x stages for 4x) -> output
conv. No batch-norm, no mean-shift RGB normalization, no 32-block/256-feature "full"
EDSR — those are tuned for 8-bit DIV2K, not 16-bit multi-band satellite reflectance.
Real learnable weights, not interpolation: `tests/test_ai_model.py` explicitly
asserts the model's output differs from a bicubic upsample of the same input, and
that gradients reach every parameter.

Configurable: `in_channels`, `num_features`, `num_res_blocks`, `scale_factor` (2 or
4 — 4x via two cascaded PixelShuffle(2) stages). Loss: **L1** (`ai/losses/reconstruction.py`)
— the standard SR baseline, less blur-prone than MSE, no auxiliary network required;
`CharbonnierLoss` is implemented as an available alternative but is not the default,
so the choice is explicit. Optimizer: AdamW.

### 18.3 Metrics — real only

`ai/metrics/image_metrics.py` implements PSNR and single-scale SSIM (Wang et al.
2004, Gaussian-window depthwise convolution) from scratch in torch — real
computation, never a placeholder. LPIPS is deliberately not implemented: it needs a
pretrained perceptual network, a meaningfully heavier dependency than this MVP's
scope justifies (the brief calls it optional "only if justified"). Critically:
**production inference never has a ground-truth HR image to compare against** — that
is the entire point of running SR — so `SuperResolutionProcessor` always sets
`metrics_available=False` and leaves psnr/ssim/lpips null for real jobs. Real
PSNR/SSIM ARE computed, but only during training/validation (`ai/training/train.py`
`validate()`) against the held-out region split.

### 18.4 Processor integration

```
ProcessingService
      |
      v
PROCESSOR_MODE (env var)
      |
      +-- 'mock' (default) -----------> MockProcessor            (Phase 3, unchanged)
      |
      +-- 'super_resolution' ---------> SuperResolutionProcessor  (this phase)
                                              |
                                              v
                                        ai/inference/infer.py -> EDSRLite + checkpoint
```

Both implement the same `BaseProcessor.run(job_id)`. Selection happens once, at
import time, in `processing_service._build_processor()` — an unknown mode is a
startup error, and `super_resolution` mode **never** falls back to `mock` if the
checkpoint is missing/broken (verified by
`test_super_resolution_never_silently_falls_back_to_mock`): the job fails with a
clear `error_message` instead. The heavy `ai.*`/torch import only happens when
`super_resolution` mode is actually selected, so a `mock`-mode deployment needs no
PyTorch installed at all.

`SuperResolutionProcessor` reuses the existing 5-stage names
(`preprocessing/feature_extraction/super_resolution/post_processing/evaluation`) for
API/frontend compatibility — real inference happens during the `super_resolution`
stage. A job's requested `scale_factor` (2 or 4, per the existing schema) is checked
against the loaded model's actual trained scale factor; a mismatch fails the job
clearly rather than silently running at the wrong scale.

**A real, documented domain-gap limitation**: the model trains on 16-bit
reflectance-scaled Sentinel-2/VENuS data (normalized /10000). Real-world inference
input is either an ordinary 8-bit upload (JPEG/PNG, normalized /255) or a Phase 5
satellite scene download — neither matches the training distribution exactly. This
is flagged explicitly in `super_resolution_processor.py` rather than silently
assumed away; closing that gap for real Sentinel-2 scenes specifically is future
work, not claimed as solved here.

### 18.5 Real vs. mocked (Phase 6)

| Area | Status |
|---|---|
| Model architecture, trained weights, tensor inference | Real |
| Training pipeline (dataset -> loader -> model -> loss -> backprop -> checkpoint) | Real, executed |
| Checkpoint save/load, config round-trip | Real, executed |
| PSNR/SSIM computation | Real formulas, executed against real held-out data where training completed |
| Processor selection / no-fallback guarantee | Real, executed via the actual job pipeline |
| Full-scale real-data training curve (loss over many real epochs) | See backend/README.md "Live SEN2VENuS + AI test" — network-dependent, reported honestly either way |
| Production inference metrics (psnr/ssim on a real job) | Not computed — no ground truth exists at inference time, by design |
| GeoTIFF/CRS preservation | Not yet — Phase 7 |

---

Phase 6 complete (see backend/README.md for the full report). Phase 7 (geospatial
processing/evaluation — Rasterio/GDAL, GeoTIFF, real production-grade PSNR/SSIM/LPIPS
pipeline) has explicitly **not** been started.
