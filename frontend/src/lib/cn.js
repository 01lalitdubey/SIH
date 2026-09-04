/** Joins truthy class name fragments, ignoring falsy values. */
export function cn(...classes) {
  return classes.filter(Boolean).join(" ");
}
