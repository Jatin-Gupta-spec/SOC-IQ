import { useEffect, useState } from "react";

const QUERY = "(prefers-reduced-motion: reduce)";

function getInitialValue(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) {
    return false;
  }
  return window.matchMedia(QUERY).matches;
}

/**
 * Reduced-motion detection foundation.
 *
 * JS-side counterpart to the `@media (prefers-reduced-motion: reduce)`
 * rule in `styles/motion.css`, for components whose motion logic can't
 * be expressed as a pure CSS transition (e.g. a component that would
 * otherwise trigger a JS-driven animation library). Per
 * `docs/architecture/12-motion-animation-architecture.md`, state-
 * changing animations should degrade to an instant change under
 * reduced motion, not disappear — this hook only reports the
 * preference; callers decide how to degrade.
 */
export function useReducedMotion(): boolean {
  const [reducedMotion, setReducedMotion] = useState<boolean>(
    getInitialValue,
  );

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) {
      return;
    }

    const mediaQueryList = window.matchMedia(QUERY);

    const handleChange = (event: MediaQueryListEvent): void => {
      setReducedMotion(event.matches);
    };

    mediaQueryList.addEventListener("change", handleChange);
    return () => mediaQueryList.removeEventListener("change", handleChange);
  }, []);

  return reducedMotion;
}
