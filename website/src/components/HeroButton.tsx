"use client";

import { type ButtonHTMLAttributes, forwardRef } from "react";
import { useAnalytics } from "@/hooks/useAnalytics";

export interface HeroButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** GTM tracking event name */
  "data-gtm-event"?: string;
  /** Optional href to make button act as a link */
  href?: string;
}

/**
 * Primary CTA button for the Hero section.
 * Displays "Start Free with BYOK" with proper states:
 * default, hover, active, disabled.
 *
 * Links to signup endpoint or shows modal (TBD).
 */
export const HeroButton = forwardRef<HTMLButtonElement, HeroButtonProps>(
  function HeroButton(
    {
      children = "Start Free with BYOK",
      disabled,
      className = "",
      onClick,
      href,
      "data-gtm-event": gtmEvent = "hero_cta_signup",
      ...props
    },
    ref,
  ) {
    const { trackEvent } = useAnalytics();

    const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
      if (gtmEvent) {
        trackEvent(gtmEvent, {
          component: "HeroButton",
          label:
            typeof children === "string" ? children : "Start Free with BYOK",
        });
      }

      if (href && !disabled) {
        window.location.href = href;
      }

      onClick?.(e);
    };

    return (
      <button
        ref={ref}
        className={`
          inline-flex items-center justify-center
          px-[var(--space-8)] py-[var(--space-4)]
          text-[length:var(--font-size-lg)] md:text-[length:var(--font-size-xl)]
          font-[var(--font-weight-bold)]
          rounded-[var(--radius-lg)]
          bg-accent text-text-inverse
          shadow-[var(--shadow-md)]
          transition-all duration-[var(--transition-base)]
          cursor-pointer
          hover:bg-accent-light hover:shadow-[var(--shadow-lg)] hover:-translate-y-0.5
          active:bg-accent-dark active:translate-y-0 active:shadow-[var(--shadow-sm)]
          focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2
          disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0 disabled:hover:shadow-[var(--shadow-md)]
          ${className}
        `}
        disabled={disabled}
        onClick={handleClick}
        data-gtm-event={gtmEvent}
        {...props}
      >
        {children}
      </button>
    );
  },
);
