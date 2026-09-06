# SRM — Deep Learning Based Super Resolution Mapping

A geospatial platform that takes medium-resolution Sentinel-2 satellite imagery
and, once the AI phase lands, upscales it to analysis-ready resolution while
preserving georeferencing (CRS, extent). Built for SIH — not a generic image
upscaler, a satellite-specific super-resolution pipeline.

## Status

Phases 0–5 of 11 are complete and verified. See [PLAN.md](PLAN.md) for the
full roadmap and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the design.

| Phase | Name | Status |
|---|---|---|
| 0 | Project Planning | ✅ Done |
| 1 | Frontend Foundation | ✅ Done |
| 2 | Animated Frontend / UI | ✅ Done |
| 3 | Backend Foundation | ✅ Done |
| 4 | Frontend ↔ Backend Integration | ✅ Done |
| 5 | Satellite Data Integration (Copernicus/Sentinel-2) | ✅ Done |
| 6 | AI Super Resolution | ⬜ Not started |
| 7 | Geospatial Processing & Evaluation | ⬜ Not started |
| 8 | Advanced Innovation | ⬜ Not started |
| 9 | Final SIH Dashboard / Demo | ⬜ Not started |
| 10 | Testing & Deployment | ⬜ Not started |

Processing (super-resolution) is currently mocked — see
[Mocked vs Real](#mocked-vs-real) below.

## Repository structure

```
SIH/
├── PLAN.md                  Full 11-phase roadmap and conventions
├── docs/ARCHITECTURE.md     Design blueprint, updated per phase
├── frontend/                React + Vite + Tailwind + Framer Motion
│   └── README.md            Frontend setup, routes, API integration notes
└── backend/                 FastAPI + PostgreSQL + SQLAlchemy
    └── README.md            Backend setup, API reference, Phase 5 satellite details
```

## Run locally

Once both servers are up (see Quickstart below), the app is here:

| URL | What it is |
|---|---|
| [http://localhost:5173](http://localhost:5173) | The app itself — start here |
| [http://localhost:8000/api/v1](http://localhost:8000/api/v1) | Backend API base |
| [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive Swagger API docs |
| [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health) | Health check (DB connectivity) |

## Quickstart

Requires Python 3.11+, Node 18+, and (optionally) Docker for Postgres — a
SQLite fallback works for local dev without it.

**Backend**

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows; `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
cp .env.example .env          # SQLite fallback works out of the box
uvicorn app.main:app --reload --port 8000
```

API: `http://localhost:8000/api/v1` · Docs: `http://localhost:8000/docs`

**Frontend**

```bash
cd frontend
npm install
cp .env.example .env          # defaults to http://localhost:8000/api/v1
npm run dev
```

App: `http://localhost:5173`

Full setup details, environment variables, and manual test logs are in
[backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md).

## Tech stack

**Frontend:** React, Vite, Tailwind CSS, Framer Motion, React Leaflet, React Router
**Backend:** FastAPI, SQLAlchemy, PostgreSQL, Pydantic, httpx
**Satellite:** Copernicus Data Space Ecosystem (Sentinel-2), OAuth2 client credentials
**Future:** PyTorch (Phase 6), Rasterio/GDAL (Phase 7)

## Mocked vs Real

| Area | This phase | Future |
|---|---|---|
| Satellite search (AOI → Sentinel-2 scenes) | **Real** — live Copernicus catalog search, selection, capped download | Full-scene/band retrieval (Phase 7+) |
| Super-resolution | Mock (Pillow resize + randomized metrics, flagged `is_mock: true`) | Real PyTorch model (Phase 6) |
| PSNR / SSIM / LPIPS | Mock (plausible random values) | Computed against ground truth (Phase 7) |
| Geospatial fidelity (GeoTIFF/CRS) | Not preserved yet | Rasterio/GDAL (Phase 7) |
| Auth | None (single demo user) | JWT, if required |

Full breakdown in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Testing

```bash
cd backend && pytest        # 39 tests, SQLite-backed, no Docker required
cd frontend && npm run build
```
