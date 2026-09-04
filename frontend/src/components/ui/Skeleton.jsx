import { cn } from "../../lib/cn";

export default function Skeleton({ className }) {
  return (
    <div
      className={cn("skeleton-shimmer rounded-md bg-surface-elevated", className)}
      aria-hidden="true"
    />
  );
}

export function SkeletonCard({ className }) {
  return (
    <div className={cn("rounded-xl border border-border bg-surface p-5", className)}>
      <div className="flex items-center justify-between">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="size-4 rounded-full" />
      </div>
      <Skeleton className="mt-3 h-7 w-16" />
    </div>
  );
}

export function SkeletonRow({ className }) {
  return (
    <div
      className={cn(
        "flex items-center justify-between rounded-xl border border-border bg-surface p-5",
        className,
      )}
    >
      <div className="flex-1 space-y-2">
        <Skeleton className="h-4 w-1/3" />
        <Skeleton className="h-3 w-1/4" />
      </div>
      <Skeleton className="h-6 w-20 rounded-full" />
    </div>
  );
}
