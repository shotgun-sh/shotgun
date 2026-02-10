"use client";

import type { ReactNode } from "react";
import { useScrollTracking } from "@/hooks/useScrollTracking";

export interface ScrollTrackerProps {
  /** The section name to track (passed to GTM as section_view event) */
  sectionName: string;
  /** Section content */
  children: ReactNode;
  /** Additional CSS classes */
  className?: string;
}

/**
 * ScrollTracker — client component wrapper that tracks scroll depth.
 *
 * Fires a GTM `section_view` event when 30% of the section
 * becomes visible in the viewport. Fires only once per section.
 */
export function ScrollTracker({
  sectionName,
  children,
  className = "",
}: ScrollTrackerProps) {
  const ref = useScrollTracking(sectionName);

  return (
    <div ref={ref as React.RefObject<HTMLDivElement>} className={className}>
      {children}
    </div>
  );
}
