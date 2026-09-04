import { useReducedMotion } from "framer-motion";
import { useMemo } from "react";
import { cn } from "../../lib/cn";

/**
 * A very subtle, lightweight star field: a fixed set of CSS-animated dots
 * (no canvas, no per-frame JS) meant to sit behind content at low opacity.
 * `count` stays small on purpose — this is atmosphere, not a hero visual.
 */
export default function StarField({ count = 40, className }) {
  const prefersReducedMotion = useReducedMotion();

  const stars = useMemo(
    () =>
      Array.from({ length: count }, (_, i) => ({
        id: i,
        top: Math.random() * 100,
        left: Math.random() * 100,
        size: Math.random() < 0.85 ? 1 : 2,
        duration: 3 + Math.random() * 4,
        delay: Math.random() * 5,
      })),
    [count],
  );

  return (
    <div
      className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}
      aria-hidden="true"
    >
      {stars.map((star) => (
        <span
          key={star.id}
          className={cn("absolute rounded-full bg-white", !prefersReducedMotion && "animate-twinkle")}
          style={{
            top: `${star.top}%`,
            left: `${star.left}%`,
            width: star.size,
            height: star.size,
            opacity: prefersReducedMotion ? 0.3 : undefined,
            animationDuration: `${star.duration}s`,
            animationDelay: `${star.delay}s`,
          }}
        />
      ))}
    </div>
  );
}
