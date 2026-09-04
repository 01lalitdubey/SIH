# SRM Platform — Frontend

React/Vite frontend for the Deep Learning Based Super Resolution Mapping
platform. As of Phase 4 it's connected to the real FastAPI backend (see
`../backend/`) — uploads, processing jobs, and results all come from the
API rather than local mock data.

## Stack

React · Vite · Tailwind CSS · Framer Motion · React Leaflet · React Router

## Setup

```bash
npm install
cp .env.example .env   # defaults to http://localhost:8000/api/v1
npm run dev
```

Requires the backend running (see `../backend/README.md`) for anything
beyond the Landing page — Dashboard, Process, and Results all call the API.

| Variable | Purpose |
|---|---|
| `VITE_API_BASE_URL` | Base URL of the backend API (e.g. `http://localhost:8000/api/v1`) |

## Routes

| Path | Page |
|---|---|
| `/` | Landing |
| `/dashboard` | Job history (from `GET /process`) |
| `/process` | New analysis: upload/AOI, configuration, live processing |
| `/results/:jobId` | Job status / results (from `GET /process/{id}` + `GET /results/{id}`) |

## API integration (Phase 4)

All backend calls go through `src/api/client.js` — no component calls
`fetch` directly. `src/lib/jobStatus.js` centralizes the mapping between
the backend's status/stage vocabulary and what the UI components expect
(e.g. backend `current_stage: "super_resolution"` → `ProcessingStages`'
`stageIndex: 2`). `src/hooks/useProcessingPoll.js` polls
`GET /process/{jobId}` every 1.2s while a job is active, stopping at
`completed`/`failed` or after repeated network failures.

Processing is still the backend's `MockProcessor` — no real AI. Metrics
stay labeled as mock/demo values in the UI.

### Manual end-to-end test log

Run via a real headless-Chromium session (Playwright) against the live
frontend + backend + database, covering the full flow specified for this
phase:

1. Open app → Landing renders
2. Navigate to New Analysis
3. Upload a real image → `POST /images/upload` → backend stores it, returns `image_id`
4. Upload UI sequences empty → uploading → "Ready for analysis" (real, not timer-driven)
5. Select AOI (rectangle draw) as an alternate source
6. Enter analysis name
7. Select scale factor (2x)
8. Confirm & Run → `POST /process`, job created
9. Processing UI appears, driven entirely by `GET /process/{id}` polling
10. Watched real stage transitions: queued → preprocessing → feature_extraction → super_resolution → post_processing → completed
11. Job completes → auto-redirect to `/results/:jobId` with the real job id
12. `GET /results/{id}` returns real metrics
13. Results page renders them, clearly labeled mock/demo
14. Before/after slider drag works, showing **real images** fetched from `/images/{id}/file` and `/results/{id}/file`
15. PSNR/SSIM/LPIPS metric cards display and animate with real values
16. Dashboard lists the job with correct name/status/scale/date, real per-job PSNR, and correct aggregate stats
17. Clicked the job row
18. → Results page opened for that exact job
19. Failure demo ("Simulate failure") → real backend failure at `super_resolution`, real `error_message` displayed, stage-by-stage failure UI
20. Invalid upload (`.txt` file) → real `415` error surfaced in the upload UI with the backend's exact message
21. Nonexistent job id (`/results/<random-uuid>`) → "Analysis not found" state
22. Backend stopped entirely → Dashboard and Results both show a clear "couldn't reach the backend" error with Retry, no infinite spinner

All 22 steps passed with **zero console/page errors** at every stage
(desktop and mobile viewports). Screenshots were captured at each step
during development.
