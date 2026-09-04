// MOCK/TEMPORARY — local placeholder data for frontend-only development.
// Replaced by real API calls to the backend in Phase 4.

export const MOCK_JOBS = [
  {
    id: "job-1042",
    name: "Coastal Delta — Sundarbans AOI",
    status: "completed",
    createdAt: "2026-09-02T09:14:00Z",
    scaleFactor: 4,
    thumbnail: null,
    metrics: { psnr: 31.8, ssim: 0.912, lpips: 0.084 },
  },
  {
    id: "job-1041",
    name: "Agricultural Belt — Punjab AOI",
    status: "processing",
    createdAt: "2026-09-03T14:02:00Z",
    scaleFactor: 2,
    thumbnail: null,
    metrics: null,
  },
  {
    id: "job-1040",
    name: "Urban Expansion — Bengaluru North",
    status: "completed",
    createdAt: "2026-08-29T06:40:00Z",
    scaleFactor: 4,
    thumbnail: null,
    metrics: { psnr: 29.4, ssim: 0.887, lpips: 0.101 },
  },
  {
    id: "job-1039",
    name: "Himalayan Glacier — Gangotri AOI",
    status: "failed",
    createdAt: "2026-08-27T11:21:00Z",
    scaleFactor: 4,
    thumbnail: null,
    metrics: null,
  },
];

export function getMockJobById(id) {
  return MOCK_JOBS.find((job) => job.id === id) ?? null;
}
