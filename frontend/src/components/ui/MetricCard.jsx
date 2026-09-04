import { motion } from "framer-motion";
import { cn } from "../../lib/cn";
import AnimatedNumber from "./AnimatedNumber";

export default function MetricCard({
  label,
  value,
  unit,
  decimals = 0,
  icon: Icon,
  hint,
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
        {Icon && <Icon className="size-4 text-accent" aria-hidden="true" />}
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
