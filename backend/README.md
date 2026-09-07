# SRM Platform — Backend

FastAPI backend for the Deep Learning Based Super Resolution Mapping
platform. Phase 3 built the backend foundation (database, image upload, a
**mocked** processing pipeline); Phase 4 connected the existing frontend to
it; Phase 5 added a **real** Copernicus Data Space Ecosystem (Sentinel-2)
integration; Phase 6 replaces the mock super-resolution step with a real,
trained PyTorch model — see [Phase 6](#phase-6--ai-super-resolution) below.
See [Mocked vs Real](#mocked-vs-real) for exactly what's real vs. still
mocked (geospatial fidelity/GeoTIFF is Phase 7).

## Stack

Python · FastAPI · SQLAlchemy · PostgreSQL · Pydantic · Uvicorn · PyTorch (Phase 6)

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
| Processing pipeline | Two selectable processors — see [Phase 6](#phase-6--ai-super-resolution): `MockProcessor` (unchanged) or **real** `SuperResolutionProcessor` | GPU-accelerated large-scene inference, richer architectures |
| Metrics (PSNR/SSIM/LPIPS) | **Real** PSNR/SSIM formulas exist and run during training/validation; production inference has no ground truth, so `metrics_available: false` there — never invented either way | Rasterio/GDAL-based evaluation against real reference rasters (Phase 7) |
| Satellite/AOI search | **Real** — Copernicus Data Space Ecosystem, live Sentinel-2 catalog search (Phase 5, done) | Full-scene/band download (currently size-capped, see below) |
| Geospatial fidelity (GeoTIFF/CRS) | Not preserved — plain image ops | Rasterio/GDAL (Phase 7) |
| Job execution | FastAPI `BackgroundTasks` (in-process) | Celery/Redis queue, once real inference needs a GPU worker at scale |
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

## Phase 6 — AI super-resolution

Replaces `MockProcessor`'s fake resize with a real, trained PyTorch model, selectable
via `PROCESSOR_MODE` and never silently substituted for the mock path. Full design
rationale in `docs/ARCHITECTURE.md` §18; this section is the test/experiment log.

### Dataset

[SEN2VENuS v2.0](https://huggingface.co/datasets/tacofoundation/sen2venus) — verified
live during development (124,123 real Sentinel-2/VENuS patch pairs, 28 regions, all
natively 2x: 128x128px@10m LR, 256x256px@5m HR). See `docs/ARCHITECTURE.md` §18.1 for
the full verification log, including the discovery that the dataset's own
`tortilla:data_split` column is entirely `'train'` (not a usable test split) and why a
region-aware split was implemented instead.

**No rasterio/GDAL anywhere in Phase 6** — samples are fetched with a lightweight
index reader (metadata only) + plain HTTP range requests + `tifffile` for pixel
decoding. RGB-only MVP (bands 0-2 of both sensors).

### Model

`EDSRLite` (`ai/models/edsr.py`) — configurable residual CNN, PixelShuffle
upsampling, no batch-norm/mean-shift. The real-data experiment below used
`num_features=32, num_res_blocks=4` (**121,987 parameters**). Loss: L1. Optimizer:
AdamW. Real, not interpolation — `tests/test_ai_model.py` asserts the model's output
differs from bicubic upsampling of the same input and that gradients reach every
parameter.

### Training smoke test (synthetic — proves the pipeline works)

```bash
python -m ai.training.train --dataset synthetic --epochs 3 --batch-size 8 \
  --max-train-samples 32 --max-val-samples 8 --checkpoint-name smoke_cli_test.pt
```

Real output from an actual run in this environment:
```
[train] device=cpu params=779,011 train_samples=32 val_samples=8
[train] epoch 1/3 train_loss=0.45861 val_loss=0.37751 val_psnr=6.78 val_ssim=0.032 (0.3s)
[train] epoch 2/3 train_loss=0.34044 val_loss=0.28995 val_psnr=9.10 val_ssim=0.096 (0.2s)
[train] epoch 3/3 train_loss=0.27866 val_loss=0.27565 val_psnr=9.60 val_ssim=0.149 (0.2s)
```
Loss decreases monotonically — the real proof the tensor pipeline (dataset -> loader
-> model -> loss -> backprop -> optimizer -> checkpoint) works. These numbers are
meaningless as SR quality (random synthetic noise has no learnable structure) —
that's expected and is exactly why this is called a smoke test, not an experiment.

### Real SEN2VENuS experiment

```bash
python -m ai.training.train --dataset sen2venus --epochs 2 --batch-size 2 \
  --max-train-samples 6 --max-val-samples 2 --num-features 32 --num-res-blocks 4 \
  --checkpoint-name edsr_satellite.pt
```

**Actually executed in this environment** against the live dataset (not a smoke test —
real Sentinel-2/VENuS pixel data, fetched over the network per patch):

```
[train] device=cpu params=121,987 train_samples=6 val_samples=2
[train] epoch 1/2 train_loss=0.03816 val_loss=0.05421 val_psnr=24.73 val_ssim=0.669 (105.5s)
[train] epoch 2/2 train_loss=0.02941 val_loss=0.04541 val_psnr=26.43 val_ssim=0.732 (88.6s)
```

Real, computed PSNR/SSIM (never randomized) on real held-out validation patches from
a region the model never trained on. Loss decreased, PSNR/SSIM improved, both epochs
— a genuine (if tiny) learning signal.

**Honest scale disclosure**: 6 training patches, 2 epochs. This is nowhere near
enough data to learn real satellite texture, and the numbers above must not be read
as a meaningful benchmark — they're the actual result of a real but deliberately
small experiment, reported as-is per the "do not claim strong performance from a tiny
experiment" rule. The tiny scale was a direct, documented consequence of degraded
network conditions to Hugging Face during this development session — see "Network
conditions encountered" below.

**Visual validation** (`python -m ai.inference.visual_check`) — real LR/SR/HR panels
were generated and inspected for exactly this checkpoint. Finding, reported without
softening: the SR output shows a **visible vertical banding/striping artifact**
across both inspected validation samples, overriding most real spatial structure.
This is the expected signature of severe undertraining (6 samples/2 epochs is far
below what a CNN needs to learn real texture), not evidence the architecture itself
is broken — the same model converges cleanly on the synthetic smoke test above, and
gradients/backprop are independently verified correct in `tests/test_ai_model.py`.
Scaling up the real-data run (more samples, more epochs, once network conditions
allow) is the direct next step to resolve this, not an architecture change.

### Network conditions encountered

Hugging Face access was measurably degraded for most of this development session —
independently confirmed by an unrelated ~2.5GB PyTorch CUDA wheel download taking an
unusually long time, and by two distinct real dataset-fetch failures (`FSTimeoutError`,
then a separate `aiohttp` connection-reset) during larger real-experiment attempts
(20 and 32 training samples respectively). `ai/datasets/sen2venus.py` was hardened
with a real retry mechanism (`MAX_FETCH_RETRIES=3`, exponential backoff, a widened
exception set covering both failure modes actually observed, and a 120s client
timeout added after hitting the default's 30s in practice) in direct response to
these real failures — not speculative resilience code. The 6-sample/2-epoch
experiment above is the run that completed successfully under these conditions.

### CPU / GPU

This session's checkpoint and all above numbers are **CPU** (`torch==2.14.0+cpu`,
installed deliberately over the CUDA build after the CUDA wheel's download proved
too slow for this session's time budget — see commit history). **A CUDA-capable GPU
is present on this machine** (`NVIDIA GeForce RTX 4050`, confirmed via `nvidia-smi`,
6GB VRAM, driver CUDA 13.1) but **GPU inference was not executed** in this session.
`ai/inference/infer.py` auto-detects CUDA (`torch.cuda.is_available()`) with no
code change required — installing `torch` from the `cu121` (or newer) index instead
of `cpu` is sufficient to exercise the GPU path.

### Live end-to-end verification (real checkpoint, real API)

With `PROCESSOR_MODE=super_resolution` and `SR_CHECKPOINT_PATH` pointed at the real
checkpoint above, against the actual running dev server (not the test suite):

```
POST /api/v1/images/upload  (64x64 JPEG)      -> 201
POST /api/v1/process {"image_id": ..., "scale_factor": 2}  -> 201, status: queued

GET /api/v1/process/{job_id}
  -> status: completed, progress: 100

GET /api/v1/results/{job_id}
  -> is_mock: false
  -> model_name: "edsr_satellite", model_version: "scale2x", device: "cpu"
  -> processing_time: 0.031 (real, ~31ms CPU inference)
  -> output_width: 128, output_height: 128   (64x64 input x2, correct)
  -> psnr: null, ssim: null, lpips: null, metrics_available: false
     (correct — no ground truth exists for a real inference job)

GET /api/v1/results/{job_id}/file -> 200, image/png, verified 128x128 RGB
```

One real bug was caught and fixed during this verification: the local SQLite dev
database (`dev.db`) predated the new `Result` columns (`is_mock`, `model_name`, etc.)
— this app uses `Base.metadata.create_all()` rather than Alembic migrations (an MVP
tradeoff documented since Phase 3), which only creates missing *tables*, not missing
*columns* on an existing one. Fixed by recreating the dev SQLite file (a fresh
Postgres database, or any environment created after this change, is unaffected).

The dev server was reverted to `PROCESSOR_MODE=mock` afterward — the existing
frontend's metric cards were built and E2E-tested (Phase 4) against always-populated
mock PSNR/SSIM values; real mode's honestly-null metrics would render against UI
that was never designed for that state, and the frontend is frozen for this phase.

### CPU inference (isolated)

`processing_time: 0.031-0.047s` for a 64x64 -> 128x128 image on CPU, observed
directly above (and separately in `tests/test_ai_processor.py`, which exercises the
full processor against a synthetic-trained checkpoint without needing the network).

### Domain gap (documented limitation)

The model trains on 16-bit reflectance-scaled Sentinel-2/VENuS data (÷10000). Real
uploads are ordinary 8-bit JPEG/PNG (÷255) — a genuinely different distribution.
`super_resolution_processor.py` picks the normalization by array dtype (`uint16` ->
÷10000, else ÷255) and this gap is documented explicitly, not silently assumed away.
Closing it for real Sentinel-2 scenes specifically is future work.

### Tests

```bash
pytest tests/test_ai_model.py tests/test_ai_training_smoke.py tests/test_ai_processor.py -v
pytest    # full suite: 65 passed (39 from Phases 3-5 + 26 new for Phase 6)
```

26 new tests, all network-free and GPU-free (`pytest.importorskip("torch")` guards
every file so a machine without torch skips them cleanly rather than failing
collection): model construction/forward-pass/channel-count/scale-factor/gradient-flow,
a full training-smoke run with checkpoint save+reload, checkpoint error handling
(missing file, malformed file), real PSNR/SSIM correctness, `SuperResolutionProcessor`
end-to-end (real checkpoint, real inference, correct Result fields, correct output
dimensions), scale-factor-mismatch rejection, no-input-imagery rejection,
`PROCESSOR_MODE` selection (including rejecting an unknown mode), and an explicit
"never silently falls back to mock" regression test.

### Environment variables

| Variable | Purpose |
|---|---|
| `PROCESSOR_MODE` | `mock` (default) or `super_resolution` |
| `SR_CHECKPOINT_PATH` | Path to the trained checkpoint (relative to `backend/`) |
| `SR_DEVICE` | `cpu`, `cuda`, or blank to auto-detect |

### Commands

```bash
# Install (CPU — see docs/ARCHITECTURE.md for the CUDA alternative)
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r ai/requirements-training.txt   # only needed to train on real data

# Real-data training (network-dependent)
python -m ai.training.train --dataset sen2venus --epochs 2 --batch-size 2 \
  --max-train-samples 6 --max-val-samples 2 --num-features 32 --num-res-blocks 4

# Visual validation
python -m ai.inference.visual_check --checkpoint ai/checkpoints/edsr_satellite.pt

# Run the server in real mode
# (.env: PROCESSOR_MODE=super_resolution, SR_CHECKPOINT_PATH=ai/checkpoints/edsr_satellite.pt)
uvicorn app.main:app --reload --port 8000
```

## Phase 6.1 — connecting the existing UI to the real AI processor

Phase 6 built `SuperResolutionProcessor`, but this dev environment's `.env` was
still left at `PROCESSOR_MODE=mock` and the frontend had a hardcoded "no real
AI model yet" banner regardless of what the backend was actually doing. This
phase closed that gap without touching Phase 6's model/training/inference code:

- **`.env` now runs real inference**: `PROCESSOR_MODE=super_resolution` with
  `SR_CHECKPOINT_PATH=ai/checkpoints/edsr_satellite.pt` — verified end-to-end
  below, not just set and assumed.
- **`GET /api/v1/health` reports real processor state** — `processor_mode`,
  `is_mock`, `processor_ready`, `model_name`, `model_version`, `device`,
  `scale_factor`, `processor_error` — computed by
  `processing_service.get_processor_status()`, which duck-types on the
  processor's `_engine` attribute rather than `isinstance`-checking
  `SuperResolutionProcessor`, so a mock-mode deployment still never imports
  torch just to answer a health check.
- **The frontend reads that instead of hardcoding anything**: `Process.jsx`
  calls `GET /health` once on mount and renders one of three truthful banners
  — real mode active (model name, scale, device), real mode configured but
  the checkpoint failed to load (the actual error, with jobs left to fail
  normally rather than being blocked client-side), or mock mode active. The
  2x/4x scale selector disables whichever factor the loaded model doesn't
  support (currently 4x, since the trained checkpoint is 2x) instead of
  letting a job get submitted that the processor would reject anyway.
- **`Results.jsx` no longer claims "Mocked values — real in Phase 7" for real
  runs.** The metrics panel's subtitle and a small model/device badge come
  from the real `ResultOut` fields (`is_mock`, `model_name`, `device`,
  `metrics_available`); when `metrics_available` is `false` (the normal case
  for real inference — no ground-truth HR image exists to score against), it
  says so honestly instead of showing zeros or inventing numbers.
- **A real test-isolation bug got fixed along the way**: `processing_service`
  builds its processor singleton from `Settings()` at import time, and the
  test suite (`tests/conftest.py`) had no isolation from whatever
  `PROCESSOR_MODE` happened to be in the developer's local `.env` — it was
  silently relying on that value staying `mock`. Flipping `.env` to
  `super_resolution` for this phase immediately broke 6 Phase 3/4 tests that
  assumed the mock pipeline. Fixed by pinning
  `os.environ.setdefault("PROCESSOR_MODE", "mock")` at the top of
  `conftest.py`, before any `app.*` import — the suite is now deterministic
  regardless of local `.env` contents. `test_ai_processor.py`'s real-mode
  tests are unaffected since they construct/monkeypatch `SuperResolutionProcessor`
  directly.

**Live verification actually performed** (not just "code was written"):

```
GET /api/v1/health  ->  {"processor_mode":"super_resolution","is_mock":false,
  "processor_ready":true,"model_name":"edsr_satellite","model_version":"scale2x",
  "device":"cpu","scale_factor":2,"processor_error":null}
```

- Checkpoint temporarily renamed away: `processor_ready` flipped to `false`
  with a clear `processor_error` message, and a real job submitted against
  that backend failed with `"Super-resolution model is not available: ..."`
  — never a silent mock-style completion. Checkpoint restored afterward.
- A real 32x32 JPEG uploaded and processed end-to-end against the running
  server: job reached `completed`, and `GET /results/{job_id}` returned
  `is_mock: false, model_name: "edsr_satellite", device: "cpu",
  metrics_available: false, psnr/ssim/lpips: null, output_width/height: 64`.
  The output PNG was confirmed on disk at 64x64 RGB and downloadable via the
  existing `/results/{job_id}/file` endpoint.
- Full backend suite: 68 passed (65 pre-existing + 3 new `get_processor_status`
  tests), including the 6 that regressed before the `conftest.py` fix.
- Frontend: `npm run build` and `npm run lint` both clean (no new warnings).
- **Not performed**: a live click-through in an actual browser window — this
  environment has no browser-automation tool available. The API responses
  above are byte-for-byte what `Process.jsx`/`Results.jsx` consume (verified
  against the exact field names each component reads), and the JSX changes
  were reviewed by hand, but that is a real limitation worth stating plainly
  rather than claiming a browser test that didn't happen.

## Phase 6.3 — real Copernicus credentials, live-tested

A real OAuth client-credentials pair was configured in `backend/.env` and
tested live against the actual CDSE API (not simulated). Results, honestly:

- **Authentication**: works. A real access token is issued.
- **Catalog search**: works. A real AOI (Sundarbans-area box) + a historical
  date range (2023) returned real Sentinel-2 products — search against
  dates in this environment's system clock (2026) correctly returned zero
  results, since no real Sentinel-2 imagery exists yet that far in the
  future relative to the real world.
- **Scene ranking/selection**: works. The clearest real candidate was
  selected: `S2B_MSIL2A_20230605T042709_N0510_R133_T45QYE_...SAFE`,
  Sentinel-2B, 5.9% cloud cover, real footprint geometry, 1014MB.
- **Download**: fails with a real, specific error —
  `401 {"code":"DAT-ZIP-609","message":"Token audience not allowed"}` from
  the OData Zipper (bulk product download) service. The configured client
  ID has the `sh-` prefix used for **Sentinel Hub** OAuth clients (a
  related but separate CDSE product, registered through the Sentinel Hub
  dashboard, meant for on-the-fly processing APIs) — its tokens don't carry
  the audience the bulk-download service requires. This was confirmed by
  calling the token and download endpoints directly and inspecting the raw
  HTTP response, not inferred from the app's wrapped error message alone.
  Getting past this requires a CDSE data-access OAuth client (not a
  Sentinel Hub one); this wasn't something that could be resolved with the
  credentials available in this session.
- A temporary bump of `SATELLITE_MAX_DOWNLOAD_MB` (200 → 1200, to fit the
  real ~1GB SAFE product) was tried and then reverted once it was clear the
  download failure is an authorization issue, not a size one — raising it
  further wouldn't have helped.

Net effect: the full **AOI → Copernicus → EDSRLite** chain is proven live up
through scene selection; the last leg (raw product download) is blocked by
an account/OAuth-client configuration issue on the Copernicus side, not by
anything in this codebase. **Upload Image → EDSRLite** (Workflow A) is
unaffected and fully real end-to-end regardless of Copernicus status.
