import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";
import { useMemo } from "react";
import { cn } from "../../lib/cn";

const VARIANTS = {
  primary:
    "bg-accent text-bg hover:bg-accent-strong shadow-[0_0_0_1px_rgba(34,211,238,0.4)]",
  secondary:
    "bg-surface-elevated text-text-primary border border-border-strong hover:border-accent/60 hover:bg-surface-hover",
  ghost: "bg-transparent text-text-secondary hover:text-text-primary hover:bg-surface-hover",
  danger: "bg-danger/10 text-danger border border-danger/40 hover:bg-danger/20",
};

const SIZES = {
  sm: "h-8 px-3 text-sm",
  md: "h-10 px-4 text-sm",
  lg: "h-12 px-6 text-base",
};

export default function Button({
  as: Component = "button",
  variant = "primary",
  size = "md",
  icon: Icon,
  loading = false,
  disabled = false,
  className,
  children,
  ...props
}) {
  const MotionComponent = useMemo(() => motion.create(Component), [Component]);
  const isDisabled = disabled || loading;

  return (
    <MotionComponent
      disabled={isDisabled}
      whileHover={isDisabled ? undefined : { scale: 1.02 }}
      whileTap={isDisabled ? undefined : { scale: 0.97 }}
      transition={{ duration: 0.12 }}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors duration-150",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...props}
    >
      {loading ? (
        <Loader2 className="size-4 animate-spin" aria-hidden="true" />
      ) : (
        Icon && <Icon className="size-4" aria-hidden="true" />
      )}
      {children}
    </MotionComponent>
  );
}
