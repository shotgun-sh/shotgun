"use client";

import { useCallback } from "react";

/**
 * GTM Event Payload structure.
 * All CTA elements should fire events with this shape.
 */
export interface GTMEventPayload {
  event: string;
  component?: string;
  variant?: string;
  label?: string;
  section?: string;
  [key: string]: unknown;
}

/**
 * Analytics tracking hook for GTM data-attributes.
 *
 * Usage:
 * ```tsx
 * const { trackEvent } = useAnalytics();
 *
 * <button
 *   data-gtm-event="hero_cta_signup"
 *   onClick={() => trackEvent("hero_cta_signup", { component: "Button" })}
 * >
 *   Start Free
 * </button>
 * ```
 *
 * This hook provides scaffolding for GTM tracking.
 * It logs events to the console in development and pushes to
 * the GTM dataLayer when available.
 */
export function useAnalytics() {
  const trackEvent = useCallback(
    (eventName: string, data?: Record<string, unknown>) => {
      const payload: GTMEventPayload = {
        event: eventName,
        ...data,
      };

      // Log to console in development for debugging
      if (process.env.NODE_ENV === "development") {
        console.log("[GTM Event]", payload);
      }

      // Push to GTM dataLayer if available
      if (typeof window !== "undefined" && window.dataLayer) {
        window.dataLayer.push(payload);
      }
    },
    [],
  );

  const trackSectionView = useCallback(
    (sectionName: string) => {
      trackEvent("section_view", { section: sectionName });
    },
    [trackEvent],
  );

  const trackCTAClick = useCallback(
    (ctaName: string, ctaVariant?: string) => {
      trackEvent("cta_click", {
        cta_name: ctaName,
        cta_variant: ctaVariant,
      });
    },
    [trackEvent],
  );

  const trackCodeCopy = useCallback(
    (codeContent: string, location?: string) => {
      trackEvent("code_copy", {
        code: codeContent,
        location,
      });
    },
    [trackEvent],
  );

  return {
    trackEvent,
    trackSectionView,
    trackCTAClick,
    trackCodeCopy,
  };
}
