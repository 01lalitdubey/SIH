import { motion, useReducedMotion } from "framer-motion";
import { Satellite } from "lucide-react";

// Data particles converge from the outer field toward the globe, evoking
// satellite data being captured/downlinked — not literal physics.
const DATA_PARTICLES = [
  { angle: 20, distance: 230, size: 3, delay: 0 },
  { angle: 95, distance: 260, size: 2, delay: 0.9 },
  { angle: 160, distance: 210, size: 2, delay: 1.8 },
  { angle: 210, distance: 250, size: 3, delay: 0.4 },
  { angle: 275, distance: 220, size: 2, delay: 1.3 },
  { angle: 330, distance: 240, size: 2, delay: 2.2 },
];

function DataParticle({ angle, distance, size, delay, reduced }) {
  const rad = (angle * Math.PI) / 180;
  const startX = Math.cos(rad) * distance;
  const startY = Math.sin(rad) * distance;

  return (
    <motion.span
      className="absolute left-1/2 top-1/2 rounded-full bg-accent"
      style={{ width: size, height: size }}
      initial={{ x: startX, y: startY, opacity: 0 }}
      animate={
        reduced
          ? { x: startX, y: startY, opacity: 0.5 }
          : { x: [startX, 0], y: [startY, 0], opacity: [0, 0.9, 0] }
      }
      transition={{ repeat: reduced ? 0 : Infinity, duration: 3.2, delay, ease: "easeIn" }}
    />
  );
}

/** Wireframe globe: a few intersecting ellipses suggesting latitude/longitude. */
function GlobeWireframe() {
  return (
    <svg viewBox="0 0 100 100" className="size-full overflow-visible">
      <defs>
        <radialGradient id="globe-sphere" cx="35%" cy="32%" r="75%">
          <stop offset="0%" stopColor="#2d5872" />
          <stop offset="50%" stopColor="#173248" />
          <stop offset="100%" stopColor="#0c1b2c" />
        </radialGradient>
      </defs>
      {/* rim glow so the sphere reads as a distinct object against the page bg */}
      <circle cx="50" cy="50" r="47.5" fill="none" stroke="#22d3ee" strokeOpacity="0.25" strokeWidth="1.5" />
      <circle cx="50" cy="50" r="46" fill="url(#globe-sphere)" stroke="#4a5a7a" strokeWidth="0.6" />
      <g stroke="#5fd9f0" strokeOpacity="0.55" fill="none" strokeWidth="0.5">
        <ellipse cx="50" cy="50" rx="46" ry="16" />
        <ellipse cx="50" cy="50" rx="46" ry="30" />
        <ellipse cx="50" cy="50" rx="20" ry="46" />
        <ellipse cx="50" cy="50" rx="38" ry="46" />
        <line x1="50" y1="4" x2="50" y2="96" strokeOpacity="0.4" />
        <line x1="4" y1="50" x2="96" y2="50" strokeOpacity="0.4" />
      </g>
    </svg>
  );
}

export default function OrbitVisual() {
  const prefersReducedMotion = useReducedMotion();

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.92 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.8, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
      className="pointer-events-none absolute inset-0 -z-10 overflow-hidden"
      aria-hidden="true"
    >
      {/* ambient glow */}
      <div className="absolute left-1/2 top-1/2 size-[560px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent/5 blur-3xl" />

      <div className="absolute left-1/2 top-1/2 flex -translate-x-1/2 -translate-y-1/2 items-center justify-center">
        {/* globe */}
        <motion.div
          className="size-[220px] overflow-hidden rounded-full shadow-[0_0_60px_rgba(34,211,238,0.12)]"
          animate={prefersReducedMotion ? undefined : { rotate: 360 }}
          transition={{ repeat: Infinity, duration: 90, ease: "linear" }}
        >
          <GlobeWireframe />
        </motion.div>

        {/* data particles converging on the globe */}
        {DATA_PARTICLES.map((p, i) => (
          <DataParticle key={i} {...p} reduced={prefersReducedMotion} />
        ))}

        {/* orbit ring + satellite + scan beam, all co-rotating */}
        <motion.div
          className="absolute size-[320px] rounded-full border border-dashed border-border-strong/40"
          animate={prefersReducedMotion ? undefined : { rotate: 360 }}
          transition={{ repeat: Infinity, duration: 34, ease: "linear" }}
        >
          {/* faint trailing arc behind the satellite */}
          <svg viewBox="0 0 100 100" className="absolute inset-0 size-full">
            <path
              d="M 50 2 A 48 48 0 0 0 15 15"
              fill="none"
              stroke="#22d3ee"
              strokeOpacity="0.3"
              strokeWidth="1"
              strokeLinecap="round"
            />
          </svg>

          <div className="absolute -top-2.5 left-1/2 flex size-9 -translate-x-1/2 items-center justify-center rounded-full border border-accent/40 bg-bg-elevated shadow-[0_0_20px_rgba(34,211,238,0.35)]">
            <Satellite className="size-4 text-accent" />
          </div>

          {/* scan beam pointing from satellite toward the globe center */}
          {!prefersReducedMotion && (
            <motion.div
              className="absolute left-1/2 top-2 h-[130px] w-px -translate-x-1/2 bg-gradient-to-b from-accent/70 to-transparent"
              style={{ transformOrigin: "top" }}
              animate={{ opacity: [0, 0.8, 0], scaleY: [0.6, 1, 0.6] }}
              transition={{ repeat: Infinity, duration: 3, ease: "easeInOut" }}
            />
          )}
        </motion.div>
      </div>

      {/* wide scan sweep across the whole hero */}
      {!prefersReducedMotion && (
        <motion.div
          className="absolute inset-x-0 h-px bg-gradient-to-r from-transparent via-accent/40 to-transparent"
          initial={{ top: "10%", opacity: 0 }}
          animate={{ top: ["10%", "90%"], opacity: [0, 1, 0] }}
          transition={{ repeat: Infinity, duration: 6, ease: "easeInOut" }}
        />
      )}
    </motion.div>
  );
}
