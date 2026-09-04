import { cn } from "../../lib/cn";

export default function MetricCard({ label, value, unit, icon: Icon, hint, className }) {
  const isPlaceholder = value === null || value === undefined;

  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-surface p-4",
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
          {isPlaceholder ? "—" : value}
        </span>
        {!isPlaceholder && unit && (
          <span className="text-sm text-text-secondary">{unit}</span>
        )}
      </div>
      {hint && <p className="mt-1 text-xs text-text-muted">{hint}</p>}
    </div>
  );
}
