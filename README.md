# SRM — Deep Learning Based Super Resolution Mapping

A geospatial platform that takes medium-resolution Sentinel-2 satellite imagery
and, once the AI phase lands, upscales it to analysis-ready resolution while
preserving georeferencing (CRS, extent). Built for SIH — not a generic image
upscaler, a satellite-specific super-resolution pipeline.

## Status

Phases 0–6 of 11 are complete and verified. See [PLAN.md](PLAN.md) for the
full roadmap and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the design.

| Phase | Name | Status |
|---|---|---|
| 0 | Project Planning | ✅ Done |
| 1 | Frontend Foundation | ✅ Done |
| 2 | Animated Frontend / UI | ✅ Done |
| 3 | Backend Foundation | ✅ Done |
| 4 | Frontend ↔ Backend Integration | ✅ Done |
| 5 | Satellite Data Integration (Copernicus/Sentinel-2) | ✅ Done |
| 6 | AI Super Resolution (real PyTorch EDSRLite, wired end-to-end) | ✅ Done |
| 7 | Geospatial Processing & Evaluation | ⬜ Not started |
| 8 | Advanced Innovation | ⬜ Not started |
| 9 | Final SIH Dashboard / Demo | ⬜ Not started |
| 10 | Testing & Deployment | ⬜ Not started |

Super-resolution can now run a real trained PyTorch model
(`PROCESSOR_MODE=super_resolution`) instead of the mock pipeline — a fresh
clone still defaults to `mock` (no PyTorch/checkpoint required) so the app
runs out of the box; see [Mocked vs Real](#mocked-vs-real) below for exactly
what's real vs. still mocked, and the checkpoint setup step in Quickstart to
switch a machine over to real mode.

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
cp .env.example .env          # SQLite fallback works out of the box, PROCESSOR_MODE=mock by default
uvicorn app.main:app --reload --port 8000
```

API: `http://localhost:8000/api/v1` · Docs: `http://localhost:8000/docs`

The steps above run the app with `PROCESSOR_MODE=mock` (no PyTorch needed) —
enough to click through the whole app end-to-end. To get **real** AI
super-resolution instead of the mock pipeline:

```bash
pip install torch   # CPU build; see backend/README.md for the CUDA install
```

then set `PROCESSOR_MODE=super_resolution` in `backend/.env` and make sure
`ai/checkpoints/edsr_satellite.pt` exists — it's gitignored (a trained model
is a local artifact, not source), so either train your own
(`python -m ai.training.train --dataset sen2venus`, see backend/README.md
"Phase 6") or copy a teammate's checkpoint file into that path directly.
Without a checkpoint, real mode still starts cleanly but fails jobs with a
clear "model not available" error rather than pretending to work.

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
**AI:** PyTorch — EDSRLite, a real residual CNN trained on the SEN2VENuS Sentinel-2/VENuS dataset
**Future:** Rasterio/GDAL, georeferencing (Phase 7)

## Mocked vs Real

| Area | Status |
|---|---|
| Satellite search (AOI → Sentinel-2 scenes) | **Real** — live Copernicus catalog search, ranking, selection; download live-verified up through scene selection (see backend/README.md "Phase 6.3" for the current account-side blocker on bulk download) |
| Super-resolution | **Real** when `PROCESSOR_MODE=super_resolution` — trained EDSRLite model, real tensor inference, `is_mock: false`. Defaults to `PROCESSOR_MODE=mock` (Pillow resize + randomized metrics) on a fresh clone, so it runs with no PyTorch/checkpoint required |
| PSNR / SSIM / LPIPS | Real when computed (training/validation, against held-out data) — `null` for a live inference job, since there's no ground-truth HR image to score against; the UI says so honestly rather than showing zeros |
| Geospatial fidelity (GeoTIFF/CRS) | Not preserved yet — planned for Phase 7 (Rasterio/GDAL) |
| Auth | None (single demo user) — JWT planned if required |

Full breakdown in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Testing

```bash
cd backend && pytest        # 71 tests, SQLite-backed, no Docker required
                             # (AI-related tests skip automatically if torch isn't installed)
cd frontend && npm run build && npm run lint
```
