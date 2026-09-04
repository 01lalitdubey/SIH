// Reusable Framer Motion variants/transitions shared across the app so
// animation timing and easing stay consistent instead of being redefined
// per component. Import what's needed rather than spreading whole objects
// where only a couple of keys are used.

export const EASE_OUT = [0.16, 1, 0.3, 1];

export const fadeIn = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.4, ease: EASE_OUT } },
};

export const slideUp = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.45, ease: EASE_OUT } },
};

export const slideDown = {
  hidden: { opacity: 0, y: -16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.45, ease: EASE_OUT } },
};

export const slideRight = {
  hidden: { opacity: 0, x: -16 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.45, ease: EASE_OUT } },
};

export const scaleIn = {
  hidden: { opacity: 0, scale: 0.94 },
  visible: { opacity: 1, scale: 1, transition: { duration: 0.35, ease: EASE_OUT } },
};

/** Wrap children in matching `visible`/`hidden` variants to stagger them. */
export function staggerContainer(staggerChildren = 0.07, delayChildren = 0) {
  return {
    hidden: {},
    visible: { transition: { staggerChildren, delayChildren } },
  };
}

/** Applied to the outermost element of a routed page for a consistent feel. */
export const pageTransition = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -10 },
  transition: { duration: 0.22, ease: EASE_OUT },
};

/** A slow, subtle breathing pulse — for "live" indicators, not attention-grabbing. */
export const pulse = {
  animate: { opacity: [0.5, 1, 0.5] },
  transition: { duration: 2.2, repeat: Infinity, ease: "easeInOut" },
};

/** A single sweep pass, e.g. a radar/scan line. */
export const scan = {
  animate: { opacity: [0, 1, 0] },
  transition: { duration: 2.6, repeat: Infinity, ease: "easeInOut" },
};
