import { cn } from "../../lib/cn";

export default function Card({ as: Component = "div", className, children, ...props }) {
  return (
    <Component
      className={cn(
        "rounded-xl border border-border bg-surface p-5",
        "transition-colors duration-150",
        className,
      )}
      {...props}
    >
      {children}
    </Component>
  );
}

export function CardHeader({ title, subtitle, action, className }) {
  return (
    <div className={cn("mb-4 flex items-start justify-between gap-3", className)}>
      <div>
        <h3 className="font-display text-base font-semibold text-text-primary">{title}</h3>
        {subtitle && <p className="mt-1 text-sm text-text-secondary">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}
