import { MoveHorizontal, Satellite, Sparkles } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import { cn } from "../../lib/cn";

function Placeholder({ variant, label }) {
  const isAfter = variant === "after";
  return (
    <div
      className={cn(
        "scan-grid-bg relative flex size-full flex-col items-center justify-center gap-2 text-text-muted",
        isAfter && "brightness-110",
      )}
    >
      {isAfter ? (
        <Sparkles className="size-8 text-accent/70" aria-hidden="true" />
      ) : (
        <Satellite className="size-8 blur-[0.5px]" aria-hidden="true" />
      )}
      {/* Corner-anchored (not centered) so the label stays visible no matter
          where the comparison handle clips this layer. */}
      <span
        className={cn(
          "absolute top-2 rounded-md border border-border-strong bg-bg/80 px-2 py-1 text-xs font-medium backdrop-blur",
          isAfter ? "right-2" : "left-2",
        )}
      >
        {label}
      </span>
    </div>
  );
}

export default function CompareSlider({
  beforeLabel = "Before — Medium Resolution",
  afterLabel = "After — Super-Resolved (MOCK)",
  className,
}) {
  const containerRef = useRef(null);
  const draggingRef = useRef(false);
  const [position, setPosition] = useState(50);

  const updateFromClientX = useCallback((clientX) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect || rect.width === 0) return;
    const pct = ((clientX - rect.left) / rect.width) * 100;
    setPosition(Math.min(100, Math.max(0, pct)));
  }, []);

  function handlePointerDown(e) {
    draggingRef.current = true;
    e.currentTarget.setPointerCapture(e.pointerId);
    updateFromClientX(e.clientX);
  }

  function handlePointerMove(e) {
    if (!draggingRef.current) return;
    updateFromClientX(e.clientX);
  }

  function stopDragging() {
    draggingRef.current = false;
  }

  function handleKeyDown(e) {
    if (e.key === "ArrowLeft") setPosition((p) => Math.max(0, p - 5));
    if (e.key === "ArrowRight") setPosition((p) => Math.min(100, p + 5));
  }

  return (
    <div
      ref={containerRef}
      className={cn(
        "relative aspect-video select-none overflow-hidden rounded-lg border border-border bg-bg-elevated",
        className,
      )}
      onPointerMove={handlePointerMove}
      onPointerUp={stopDragging}
      onPointerLeave={stopDragging}
    >
      <div className="absolute inset-0">
        <Placeholder variant="after" label={afterLabel} />
      </div>

      <div
        className="absolute inset-0 overflow-hidden"
        style={{ clipPath: `inset(0 ${100 - position}% 0 0)` }}
      >
        <Placeholder variant="before" label={beforeLabel} />
      </div>

      <div
        className="pointer-events-none absolute inset-y-0 w-px bg-accent/80"
        style={{ left: `${position}%` }}
      />

      <div
        role="slider"
        tabIndex={0}
        aria-label="Before/after comparison position"
        aria-valuenow={Math.round(position)}
        aria-valuemin={0}
        aria-valuemax={100}
        onKeyDown={handleKeyDown}
        onPointerDown={handlePointerDown}
        className="absolute top-1/2 flex size-9 -translate-x-1/2 -translate-y-1/2 cursor-ew-resize items-center justify-center rounded-full border border-accent/60 bg-bg shadow-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        style={{ left: `${position}%` }}
      >
        <MoveHorizontal className="size-4 text-accent" aria-hidden="true" />
      </div>
    </div>
  );
}
