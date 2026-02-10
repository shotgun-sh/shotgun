"use client";

import { useEffect, useRef } from "react";
import { useAnalytics } from "@/hooks/useAnalytics";

/**
 * Hook that tracks when a section becomes visible in the viewport.
 * Uses IntersectionObserver to fire a GTM event once per section view.
 *
 * Usage:
 * ```tsx
 * const ref = useScrollTracking("problems");
 * <section ref={ref}>...</section>
 * ```
 */
export function useScrollTracking(sectionName: string) {
  const ref = useRef<HTMLElement>(null);
  const hasFired = useRef(false);
  const { trackSectionView } = useAnalytics();

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          // Fire once when 30% of the section is visible
          if (entry.isIntersecting && !hasFired.current) {
            hasFired.current = true;
            trackSectionView(sectionName);
          }
        });
      },
      { threshold: 0.3 },
    );

    observer.observe(element);

    return () => {
      observer.disconnect();
    };
  }, [sectionName, trackSectionView]);

  return ref;
}
