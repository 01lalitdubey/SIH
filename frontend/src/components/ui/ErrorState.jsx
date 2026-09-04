import { AlertTriangle, RotateCcw } from "lucide-react";
import { cn } from "../../lib/cn";
import Button from "./Button";

export default function ErrorState({
  title = "Something went wrong",
  description = "An unexpected error occurred. Please try again.",
  onRetry,
  retryLabel = "Retry",
  className,
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-xl border border-danger/30 bg-danger-soft py-16 text-center",
        className,
      )}
      role="alert"
    >
      <div className="flex size-12 items-center justify-center rounded-full border border-danger/40 bg-bg-elevated">
        <AlertTriangle className="size-5 text-danger" aria-hidden="true" />
      </div>
      <div className="space-y-1">
        <p className="font-display text-sm font-semibold text-text-primary">{title}</p>
        <p className="max-w-sm text-sm text-text-secondary">{description}</p>
      </div>
      {onRetry && (
        <Button size="sm" variant="secondary" icon={RotateCcw} onClick={onRetry} className="mt-2">
          {retryLabel}
        </Button>
      )}
    </div>
  );
}
