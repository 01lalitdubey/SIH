import { Inbox } from "lucide-react";
import { cn } from "../../lib/cn";
import Button from "./Button";

export default function EmptyState({
  icon: Icon = Inbox,
  title = "Nothing here yet",
  description,
  actionLabel,
  onAction,
  className,
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border py-16 text-center",
        className,
      )}
    >
      <div className="flex size-12 items-center justify-center rounded-full bg-surface-elevated">
        <Icon className="size-5 text-text-muted" aria-hidden="true" />
      </div>
      <div className="space-y-1">
        <p className="font-display text-sm font-semibold text-text-primary">{title}</p>
        {description && (
          <p className="max-w-sm text-sm text-text-secondary">{description}</p>
        )}
      </div>
      {actionLabel && (
        <Button size="sm" variant="secondary" onClick={onAction} className="mt-2">
          {actionLabel}
        </Button>
      )}
    </div>
  );
}
