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

// The checkpoint's stored model_name is a training-pipeline label
// (ai/training/train.py), not a display string — map the one real value
// Phase 6 produces to the architecture's actual name for the UI.
const MODEL_DISPLAY_NAMES = { edsr_satellite: "EDSRLite" };

/** Real model_name (from the health/result payload) -> a human label.
 * Falls back to the raw value so an unrecognized future model name is
 * still shown truthfully rather than hidden. */
export function displayModelName(modelName) {
  if (!modelName) return "EDSRLite";
  return MODEL_DISPLAY_NAMES[modelName] ?? modelName;
}

/**
 * Categorizes a failed job's error using signals the backend actually
 * provides — `current_stage` staying "satellite_acquisition" is set by
 * ProcessingService specifically when satellite acquisition itself failed
 * (see backend/app/services/processing_service.py), so this never has to
 * guess from message text alone for that case. Everything else falls back
 * to matching the (already specific) error_message text SuperResolutionProcessor
 * produces. Returns null for a non-failed job.
 */
export function classifyFailure(job) {
  if (!job || job.status !== "failed") return null;

  if (job.current_stage === "satellite_acquisition") {
    return { category: "satellite", title: "Satellite Acquisition Failed" };
  }

  const message = (job.error_message || "").toLowerCase();
  if (message.includes("model is not available")) {
    return { category: "model", title: "AI Model Unavailable" };
  }
  if (message.includes("ai inference failed")) {
    return { category: "inference", title: "AI Inference Failed" };
  }
  if (message.includes("only supports") && message.includes("but this job requested")) {
    return { category: "scale", title: "Unsupported Scale Factor" };
  }
  if (message.includes("no input imagery")) {
    return { category: "input", title: "No Input Imagery" };
  }
  return { category: "processing", title: "Processing Failed" };
}
