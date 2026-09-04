import { motion, useReducedMotion } from "framer-motion";
import { cn } from "../../lib/cn";
import AnimatedNumber from "./AnimatedNumber";

const RING_RADIUS = 15;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;

function MetricRing({ percent }) {
  const prefersReducedMotion = useReducedMotion();
  const clamped = Math.max(0, Math.min(100, percent));
  const offset = RING_CIRCUMFERENCE * (1 - clamped / 100);

  return (
    <svg viewBox="0 0 36 36" className="size-9 -rotate-90">
      <circle cx="18" cy="18" r={RING_RADIUS} className="fill-none stroke-border" strokeWidth="3" />
      <motion.circle
        cx="18"
        cy="18"
        r={RING_RADIUS}
        className="fill-none stroke-accent"
        strokeWidth="3"
        strokeLinecap="round"
        strokeDasharray={RING_CIRCUMFERENCE}
        initial={{ strokeDashoffset: RING_CIRCUMFERENCE }}
        animate={{ strokeDashoffset: offset }}
        transition={
          prefersReducedMotion ? { duration: 0 } : { duration: 0.9, ease: "easeOut" }
        }
      />
    </svg>
  );
}

export default function MetricCard({
  label,
  value,
  unit,
  decimals = 0,
  icon: Icon,
  hint,
  ringPercent,
  className,
}) {
  const isPlaceholder = value === null || value === undefined;
  const isNumeric = typeof value === "number";

  return (
    <motion.div
      whileHover={{ y: -2 }}
      transition={{ duration: 0.15, ease: "easeOut" }}
      className={cn(
        "rounded-xl border border-border bg-surface p-4 transition-colors hover:border-border-strong",
        className,
      )}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-text-muted">
          {label}
        </span>
        {ringPercent !== undefined && !isPlaceholder ? (
          <MetricRing percent={ringPercent} />
        ) : (
          Icon && <Icon className="size-4 text-accent" aria-hidden="true" />
        )}
      </div>
      <div className="mt-2 flex items-baseline gap-1">
        <span
          className={cn(
            "font-display text-2xl font-semibold",
            isPlaceholder ? "text-text-muted" : "text-text-primary",
          )}
        >
          {isPlaceholder ? (
            "—"
          ) : isNumeric ? (
            <AnimatedNumber value={value} decimals={decimals} />
          ) : (
            value
          )}
        </span>
        {!isPlaceholder && unit && (
          <span className="text-sm text-text-secondary">{unit}</span>
        )}
      </div>
      {hint && <p className="mt-1 text-xs text-text-muted">{hint}</p>}
    </motion.div>
  );
}
