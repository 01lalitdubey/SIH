import { motion, useReducedMotion } from "framer-motion";
import { Satellite } from "lucide-react";

const PARTICLES = [
  { top: "18%", left: "12%", size: 3, delay: 0 },
  { top: "30%", left: "82%", size: 2, delay: 0.6 },
  { top: "68%", left: "8%", size: 2, delay: 1.1 },
  { top: "78%", left: "76%", size: 3, delay: 0.3 },
  { top: "12%", left: "58%", size: 2, delay: 1.6 },
  { top: "85%", left: "42%", size: 2, delay: 0.9 },
];

export default function OrbitVisual() {
  const prefersReducedMotion = useReducedMotion();

  return (
    <div
      className="pointer-events-none absolute inset-0 -z-10 overflow-hidden"
      aria-hidden="true"
    >
      {/* ambient glow */}
      <div className="absolute left-1/2 top-1/2 size-[560px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent/5 blur-3xl" />

      {/* orbit rings */}
      <div className="absolute left-1/2 top-1/2 flex -translate-x-1/2 -translate-y-1/2 items-center justify-center">
        <div className="size-[320px] rounded-full border border-border-strong/40" />
        <motion.div
          className="absolute size-[420px] rounded-full border border-dashed border-border-strong/30"
          animate={prefersReducedMotion ? undefined : { rotate: 360 }}
          transition={{ repeat: Infinity, duration: 40, ease: "linear" }}
        >
          <div className="absolute -top-2 left-1/2 flex size-9 -translate-x-1/2 items-center justify-center rounded-full border border-accent/40 bg-bg-elevated shadow-[0_0_20px_rgba(34,211,238,0.35)]">
            <Satellite className="size-4 text-accent" />
          </div>
        </motion.div>
      </div>

      {/* scan sweep */}
      {!prefersReducedMotion && (
        <motion.div
          className="absolute inset-x-0 h-px bg-gradient-to-r from-transparent via-accent/50 to-transparent"
          initial={{ top: "10%", opacity: 0 }}
          animate={{ top: ["10%", "90%"], opacity: [0, 1, 0] }}
          transition={{ repeat: Infinity, duration: 5, ease: "easeInOut" }}
        />
      )}

      {/* particles */}
      {PARTICLES.map((p, i) => (
        <motion.span
          key={i}
          className="absolute rounded-full bg-accent/60"
          style={{ top: p.top, left: p.left, width: p.size, height: p.size }}
          animate={
            prefersReducedMotion
              ? undefined
              : { opacity: [0.2, 0.8, 0.2], y: [0, -8, 0] }
          }
          transition={{ repeat: Infinity, duration: 4 + i, delay: p.delay, ease: "easeInOut" }}
        />
      ))}
    </div>
  );
}
