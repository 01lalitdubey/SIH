import { motion } from "framer-motion";
import { useMemo } from "react";
import { cn } from "../../lib/cn";

export default function Card({
  as: Component = "div",
  interactive = false,
  className,
  children,
  ...props
}) {
  const MotionComponent = useMemo(() => motion.create(Component), [Component]);

  return (
    <MotionComponent
      whileHover={interactive ? { y: -3 } : undefined}
      whileTap={interactive ? { scale: 0.99 } : undefined}
      transition={{ duration: 0.15, ease: "easeOut" }}
      className={cn(
        "rounded-xl border border-border bg-surface p-5",
        "transition-colors duration-150 hover:border-border-strong",
        className,
      )}
      {...props}
    >
      {children}
    </MotionComponent>
  );
}

export function CardHeader({ title, subtitle, action, className }) {
  return (
    <div className={cn("mb-4 flex items-start justify-between gap-3", className)}>
      <div>
        <h3 className="font-display text-base font-semibold text-text-primary">{title}</h3>
        {subtitle && <p className="mt-1 text-sm text-text-secondary">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}
