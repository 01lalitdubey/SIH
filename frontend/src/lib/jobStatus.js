// Maps backend job status/stage vocabulary onto what the existing UI
// components expect, in one place instead of duplicating the mapping in
// every page that touches a job.

// Order must match the backend's ProcessingStage.ORDERED and the frontend's
// STAGE_LABELS (ProcessingStages.jsx) — both are 5 stages, same sequence.
const STAGE_KEYS = [
  "preprocessing",
  "feature_extraction",
  "super_resolution",
  "post_processing",
  "evaluation",
];

/** backend `current_stage` -> ProcessingStages' 0-based `stageIndex`.
 * Returns -1 for null/queued (not yet on any stage — every stage renders
 * "pending", which is the correct look for a queued job). */
export function stageKeyToIndex(stageKey) {
  if (!stageKey) return -1;
  return STAGE_KEYS.indexOf(stageKey);
}

/** backend `status` -> ProcessingStages' status prop ("processing" | "completed" | "error"). */
export function toProcessingUiStatus(backendStatus) {
  if (backendStatus === "completed") return "completed";
  if (backendStatus === "failed") return "error";
  return "processing"; // queued | processing
}

/** backend `status` -> StatusBadge's status prop (pending | processing | completed | failed). */
export function toBadgeStatus(backendStatus) {
  return backendStatus === "queued" ? "pending" : backendStatus;
}

export const TERMINAL_STATUSES = new Set(["completed", "failed"]);
