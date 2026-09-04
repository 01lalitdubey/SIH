import {
  animate,
  motion,
  useMotionValue,
  useReducedMotion,
  useTransform,
} from "framer-motion";
import { useEffect } from "react";

export default function AnimatedNumber({ value, decimals = 0, duration = 0.9, className }) {
  const prefersReducedMotion = useReducedMotion();
  const numericValue = typeof value === "number" ? value : Number(value) || 0;
  const motionValue = useMotionValue(0);
  const rounded = useTransform(motionValue, (latest) => latest.toFixed(decimals));

  useEffect(() => {
    if (prefersReducedMotion) {
      motionValue.set(numericValue);
      return;
    }
    const controls = animate(motionValue, numericValue, {
      duration,
      ease: "easeOut",
    });
    return controls.stop;
  }, [numericValue, duration, prefersReducedMotion, motionValue]);

  if (value === null || value === undefined) {
    return <span className={className}>&mdash;</span>;
  }

  return <motion.span className={className}>{rounded}</motion.span>;
}
