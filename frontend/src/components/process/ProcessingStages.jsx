import { motion, useReducedMotion } from "framer-motion";
import { Check, Loader2, X } from "lucide-react";
import { cn } from "../../lib/cn";
import IndeterminateBar from "../common/IndeterminateBar";

export const STAGE_LABELS = [
  "Preprocessing",
  "Feature Extraction",
  "Super Resolution",
  "Post Processing",
  "Evaluation",
];

function stageState(index, stageIndex, status) {
  if (status === "completed") return "complete";
  if (status === "error" && index === stageIndex) return "error";
  if (index < stageIndex) return "complete";
  if (index === stageIndex) return "active";
  return "pending";
}

function StageIcon({ state, number }) {
  if (state === "complete") {
    return (
      <div className="flex size-10 shrink-0 items-center justify-center rounded-full border border-success/40 bg-success-soft text-success">
        <Check className="size-4" aria-hidden="true" />
      </div>
    );
  }

  if (state === "error") {
    return (
      <div className="flex size-10 shrink-0 items-center justify-center rounded-full border border-danger/40 bg-danger-soft text-danger">
        <X className="size-4" aria-hidden="true" />
      </div>
    );
  }

  if (state === "active") {
    return (
      <div className="relative flex size-10 shrink-0 items-center justify-center rounded-full border border-accent/40 bg-accent-soft text-accent shadow-[0_0_16px_rgba(34,211,238,0.35)]">
        <motion.span
          className="absolute inset-0 rounded-full border border-accent/50"
          animate={{ scale: [1, 1.35], opacity: [0.6, 0] }}
          transition={{ repeat: Infinity, duration: 1.4, ease: "easeOut" }}
          aria-hidden="true"
        />
        <Loader2 className="size-4 animate-spin" aria-hidden="true" />
      </div>
    );
  }

  return (
    <div className="flex size-10 shrink-0 items-center justify-center rounded-full border border-border-strong text-text-muted">
      <span className="text-xs font-medium">{number}</span>
    </div>
  );
}

function Bookend({ label, tone }) {
  return (
    <div className="relative flex items-center gap-4">
      <div
        className={cn(
          "flex size-10 shrink-0 items-center justify-center rounded-full border font-mono text-[10px] font-medium",
          tone === "active"
            ? "border-accent/40 bg-accent-soft text-accent"
            : "border-border-strong text-text-muted",
        )}
      >
        {label === "IN" ? "IN" : "OUT"}
      </div>
      <p className={cn("text-sm font-medium", tone === "active" ? "text-text-primary" : "text-text-muted")}>
        {label === "IN" ? "Input imagery" : "Result"}
      </p>
    </div>
  );
}

/**
 * status: "processing" | "completed" | "error"
 * stageIndex: index of the currently active/failed stage (0-based)
 */
export default function ProcessingStages({ stageIndex, status = "processing" }) {
  const prefersReducedMotion = useReducedMotion();
  const totalNodes = STAGE_LABELS.length + 2; // + input/result bookends
  const completedCount =
    status === "completed" ? STAGE_LABELS.length : stageIndex + (status === "error" ? 0 : 0.5);
  const fillPercent = Math.min(100, ((completedCount + 1) / totalNodes) * 100);

  // Particle travels within the currently-filling segment of the track only.
  const segStart = ((stageIndex + 1) / totalNodes) * 100;
  const segEnd = ((stageIndex + 2) / totalNodes) * 100;

  return (
    <div className="relative pl-0">
      <div className="relative flex flex-col gap-7">
        <div className="absolute left-5 top-5 bottom-5 w-px -translate-x-1/2 bg-border-strong" />
        <motion.div
          className={cn(
            "absolute left-5 top-5 w-px -translate-x-1/2",
            status === "error" ? "bg-danger" : "bg-accent",
          )}
          initial={{ height: 0 }}
          animate={{ height: `${fillPercent}%` }}
          transition={{ duration: 0.5, ease: "easeOut" }}
        />

        {status === "processing" && !prefersReducedMotion && (
          <motion.span
            className="absolute left-5 size-1.5 -translate-x-1/2 rounded-full bg-accent shadow-[0_0_8px_rgba(34,211,238,0.8)]"
            style={{ top: "20px" }}
            animate={{ top: [`${segStart}%`, `${segEnd}%`] }}
            transition={{ repeat: Infinity, duration: 1.1, ease: "easeInOut" }}
          />
        )}

        <Bookend label="IN" tone="active" />

        {STAGE_LABELS.map((label, i) => {
          const state = stageState(i, stageIndex, status);
          return (
            <div key={label} className="relative flex items-center gap-4">
              <StageIcon state={state} number={i + 1} />
              <div className="min-w-0 flex-1">
                <p
                  className={cn(
                    "text-sm font-medium",
                    state === "pending" ? "text-text-muted" : "text-text-primary",
                  )}
                >
                  {label}
                </p>
                {state === "active" && (
                  <div className="mt-1.5 max-w-[160px]">
                    <IndeterminateBar />
                  </div>
                )}
                {state === "error" && <p className="text-xs text-danger">Failed</p>}
                {state === "complete" && <p className="text-xs text-success">Done</p>}
              </div>
            </div>
          );
        })}

        <Bookend label="OUT" tone={status === "completed" ? "active" : "pending"} />
      </div>
    </div>
  );
}
