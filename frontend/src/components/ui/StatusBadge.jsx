import { motion, useReducedMotion } from "framer-motion";
import { CheckCircle2, CircleDashed, Loader2, XCircle } from "lucide-react";
import { cn } from "../../lib/cn";

const STATUS_CONFIG = {
  pending: {
    label: "Pending",
    icon: CircleDashed,
    className: "text-text-secondary bg-surface-elevated border-border-strong",
  },
  processing: {
    label: "Processing",
    icon: Loader2,
    className: "text-accent bg-info-soft border-accent/30",
    spin: true,
    live: true,
  },
  completed: {
    label: "Completed",
    icon: CheckCircle2,
    className: "text-success bg-success-soft border-success/30",
  },
  failed: {
    label: "Failed",
    icon: XCircle,
    className: "text-danger bg-danger-soft border-danger/30",
  },
};

export default function StatusBadge({ status, className }) {
  const prefersReducedMotion = useReducedMotion();
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.pending;
  const Icon = config.icon;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
        config.className,
        className,
      )}
    >
      {config.live && (
        <span className="relative flex size-1.5">
          {!prefersReducedMotion && (
            <motion.span
              className="absolute inline-flex size-full rounded-full bg-accent"
              animate={{ scale: [1, 2.2], opacity: [0.6, 0] }}
              transition={{ repeat: Infinity, duration: 1.6, ease: "easeOut" }}
            />
          )}
          <span className="relative inline-flex size-1.5 rounded-full bg-accent" />
        </span>
      )}
      <Icon className={cn("size-3.5", config.spin && "animate-spin")} aria-hidden="true" />
      {config.label}
    </span>
  );
}
