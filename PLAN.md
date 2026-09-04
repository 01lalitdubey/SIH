# Deep Learning Based Super Resolution Mapping (SRM) from Medium Resolution Satellite Imageries

## 1. Project Summary

A professional web-based geospatial platform that takes medium-resolution satellite
imagery (Sentinel-2 via Copernicus Data Space) and, in later phases, uses deep learning
to generate higher-resolution, analysis-ready imagery while preserving geospatial
information (georeferencing, CRS, extent).

This is **not** a generic image upscaler — it is a satellite/geospatial super-resolution
platform. Every phase must respect that the input/output are geospatial rasters, not
plain images.

## 2. Repository Structure

Monorepo, single git repo at project root.

```
SIH/
├── PLAN.md                # this file
├── README.md              # top-level overview + quickstart (added when scaffold exists)
├── .gitignore
├── frontend/               # React + Vite + Tailwind app (Phase 1+)
│   ├── src/
│   ├── public/
│   └── ...
├── backend/                 # FastAPI app (Phase 3+)
│   ├── app/
│   │   ├── api/            # route modules
│   │   ├── core/           # config, settings
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas
│   │   └── services/       # business logic (geospatial, AI, satellite fetch)
│   ├── tests/
│   └── requirements.txt
└── docs/                    # architecture notes, API contracts, phase reports
```

Frontend and backend stay decoupled — communicate only via a documented REST API
(Phase 4). No shared code between them beyond documented API contracts.

## 3. Technology Stack

**Frontend:** React, Vite, Tailwind CSS, Framer Motion, React Leaflet, Lucide React,
Recharts (where needed).

**Backend:** Python, FastAPI, PostgreSQL, SQLAlchemy, Pydantic.

**Geospatial:** Rasterio, GDAL (where required), GeoTIFF, GeoPandas (where required).

**AI (Phase 6+):** PyTorch. Specific super-resolution architecture to be selected later
based on dataset, compute budget, and project goals — not decided yet.

**Satellite data:** Copernicus Data Space Ecosystem / Sentinel-2.

## 4. High-Level Architecture (target end state)

```
User (browser)
   │
   ▼
Frontend (React/Vite) ── AOI selection, before/after viewer, evaluation dashboard
   │  REST / JSON (+ file responses for GeoTIFF)
   ▼
Backend (FastAPI)
   ├── Satellite Data Service ── Copernicus Data Space API (Sentinel-2 fetch)
   ├── Preprocessing Service ── Rasterio/GDAL: reprojection, tiling, normalization
   ├── SR Inference Service ── PyTorch model (Phase 6)
   ├── Geospatial Postprocessing ── re-embed georeferencing, GeoTIFF output
   ├── Evaluation Service ── PSNR, SSIM, LPIPS
   └── PostgreSQL ── job metadata, AOI history, results tracking
```

## 5. Phase Plan (do not skip ahead)

| Phase | Name | Output |
|---|---|---|
| 0 | Project Planning | This document, repo initialized |
| 1 | Frontend Foundation | React+Vite+Tailwind app scaffolded, base layout/routing |
| 2 | Animated Frontend / UI | Framer Motion interactions, visual design system applied |
| 3 | Backend Foundation | FastAPI app scaffolded, DB models, health endpoint |
| 4 | Frontend ↔ Backend Integration | Real API calls replacing any mocks |
| 5 | Satellite Data Integration | Copernicus/Sentinel-2 fetch + AOI-based retrieval |
| 6 | AI Super Resolution | PyTorch SR model integrated into inference service |
| 7 | Geospatial Processing & Evaluation | GeoTIFF I/O, PSNR/SSIM/LPIPS metrics |
| 8 | Advanced Innovation | Satellite-specific novel feature(s) |
| 9 | Final SIH Dashboard / Demo | Polished end-to-end demo experience |
| 10 | Testing & Deployment | Test coverage, deployment pipeline |

## 6. API Contract Skeleton (placeholder — finalized in Phase 3/4)

Indicative only; will be refined once backend models exist.

```
GET  /health                        -> service status
POST /aoi                           -> create an Area of Interest
GET  /aoi/{id}                      -> fetch AOI details
POST /jobs/super-resolution         -> submit SR job for an AOI
GET  /jobs/{id}                     -> job status/result
GET  /jobs/{id}/result.tif          -> GeoTIFF result download
GET  /jobs/{id}/metrics             -> PSNR/SSIM/LPIPS for a completed job
```

## 7. Conventions

- Mocked/temporary functionality must be clearly labeled `MOCK/TEMPORARY` in code and docs.
- No AI model work before Phase 6 is explicitly started.
- Secrets (Copernicus credentials, DB URLs) via environment variables only, never hardcoded.
- Each phase ends with a report: what was implemented, files created/modified,
  dependencies added, how to run/test, known issues, what's intentionally not done,
  and whether the phase is complete.

## 8. Status

Phase 0 in progress: this plan document + git initialization. Frontend/backend scaffolds
are **not yet created** — that begins in Phase 1.
