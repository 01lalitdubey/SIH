import { motion } from "framer-motion";
import { cn } from "../../lib/cn";

/** A thin, looping progress bar for "working, duration unknown" states. */
export default function IndeterminateBar({ className, barClassName }) {
  return (
    <div
      className={cn("h-1 w-full overflow-hidden rounded-full bg-surface-elevated", className)}
    >
      <motion.div
        className={cn("h-full w-1/3 rounded-full bg-accent", barClassName)}
        initial={{ x: "-100%" }}
        animate={{ x: "300%" }}
        transition={{ repeat: Infinity, duration: 1.1, ease: "easeInOut" }}
      />
    </div>
  );
}
