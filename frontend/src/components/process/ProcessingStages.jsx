import { motion } from "framer-motion";
import { Check, Loader2, X } from "lucide-react";
import { cn } from "../../lib/cn";

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
      <div className="relative flex size-10 shrink-0 items-center justify-center rounded-full border border-accent/40 bg-accent-soft text-accent">
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

/**
 * status: "processing" | "completed" | "error"
 * stageIndex: index of the currently active/failed stage (0-based)
 */
export default function ProcessingStages({ stageIndex, status = "processing" }) {
  const completedCount =
    status === "completed" ? STAGE_LABELS.length : stageIndex + (status === "error" ? 0 : 0.5);
  const fillPercent = Math.min(100, (completedCount / STAGE_LABELS.length) * 100);

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

        {STAGE_LABELS.map((label, i) => {
          const state = stageState(i, stageIndex, status);
          return (
            <div key={label} className="relative flex items-center gap-4">
              <StageIcon state={state} number={i + 1} />
              <div>
                <p
                  className={cn(
                    "text-sm font-medium",
                    state === "pending" ? "text-text-muted" : "text-text-primary",
                  )}
                >
                  {label}
                </p>
                {state === "active" && (
                  <p className="text-xs text-accent">In progress&hellip;</p>
                )}
                {state === "error" && <p className="text-xs text-danger">Failed</p>}
                {state === "complete" && <p className="text-xs text-success">Done</p>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
