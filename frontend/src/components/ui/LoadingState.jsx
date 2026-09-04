import { motion } from "framer-motion";
import { Satellite } from "lucide-react";
import { cn } from "../../lib/cn";

export default function LoadingState({ label = "Loading", className }) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 py-16 text-text-secondary",
        className,
      )}
      role="status"
      aria-live="polite"
    >
      <motion.div
        animate={{ rotate: 360 }}
        transition={{ repeat: Infinity, duration: 2.4, ease: "linear" }}
        className="flex size-12 items-center justify-center rounded-full border border-accent/30 bg-info-soft"
      >
        <Satellite className="size-5 text-accent" aria-hidden="true" />
      </motion.div>
      <p className="text-sm">{label}&hellip;</p>
    </div>
  );
}
