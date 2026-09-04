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

- **[MOCK now]**: `POST /api/v1/aoi/search` returns a small hardcoded/fake list of
  "available scenes" for a submitted AOI (id, date, cloud cover %, thumbnail placeholder),
  so the AOI-selection UI can be fully built and tested.
- **[FUTURE, Phase 5]**: replace with real Copernicus Data Space Ecosystem
  integration — OAuth2 client credentials, product search by AOI/date/cloud-cover,
  async download of Sentinel-2 bands into storage.

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
| Satellite data | Mock AOI search results | Real Copernicus/Sentinel-2 (Phase 5) |
| Geospatial fidelity | Not preserved (plain image ops) | Rasterio/GDAL, GeoTIFF, CRS-preserving (Phase 7) |
| Storage | Local disk | S3/MinIO object storage |
| Auth | None (single demo user) | JWT-based, if required |
| Job execution | FastAPI BackgroundTasks | Celery/Redis queue |
| Metrics (PSNR/SSIM/LPIPS) | Null/placeholder in schema | Computed for real (Phase 7) |

---

Awaiting approval before Phase 1 (Frontend Foundation) begins.
