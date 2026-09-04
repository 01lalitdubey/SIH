import { ImageOff, SatelliteDish } from "lucide-react";
import { cn } from "../../lib/cn";

export default function ImageContainer({
  src,
  alt = "",
  label,
  aspect = "aspect-square",
  className,
}) {
  return (
    <div
      className={cn(
        "group relative overflow-hidden rounded-lg border border-border bg-bg-elevated",
        aspect,
        className,
      )}
    >
      {src ? (
        <img src={src} alt={alt} className="size-full object-cover" />
      ) : (
        <div className="scan-grid-bg flex size-full flex-col items-center justify-center gap-2 text-text-muted">
          <SatelliteDish className="size-8" aria-hidden="true" />
          <span className="text-xs">No imagery loaded</span>
        </div>
      )}

      {label && (
        <span className="absolute left-2 top-2 rounded-md border border-border-strong bg-bg/80 px-2 py-1 text-xs font-medium text-text-secondary backdrop-blur">
          {label}
        </span>
      )}

      {!src && (
        <ImageOff
          className="absolute right-2 top-2 size-4 text-text-muted"
          aria-hidden="true"
        />
      )}
    </div>
  );
}
