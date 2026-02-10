"use client";

import { type ButtonHTMLAttributes, forwardRef } from "react";
import { useAnalytics } from "@/hooks/useAnalytics";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Visual style variant */
  variant?: "primary" | "secondary" | "accent" | "ghost";
  /** Size of the button */
  size?: "sm" | "md" | "lg";
  /** Whether the button is in a loading state */
  loading?: boolean;
  /** GTM tracking event name */
  "data-gtm-event"?: string;
}

const variantStyles: Record<string, string> = {
  primary:
    "bg-primary text-text-inverse hover:bg-primary-light active:bg-primary-dark focus-visible:ring-2 focus-visible:ring-secondary focus-visible:ring-offset-2",
  secondary:
    "bg-secondary text-text-inverse hover:bg-secondary-light active:bg-secondary-dark focus-visible:ring-2 focus-visible:ring-secondary focus-visible:ring-offset-2",
  accent:
    "bg-accent text-text-inverse hover:bg-accent-light active:bg-accent-dark focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2",
  ghost:
    "bg-transparent text-text-primary border border-border hover:bg-surface active:bg-border-light focus-visible:ring-2 focus-visible:ring-secondary focus-visible:ring-offset-2",
};

const sizeStyles: Record<string, string> = {
  sm: "px-[var(--space-3)] py-[var(--space-1)] text-[length:var(--font-size-sm)] rounded-[var(--radius-md)]",
  md: "px-[var(--space-5)] py-[var(--space-2)] text-[length:var(--font-size-base)] rounded-[var(--radius-md)]",
  lg: "px-[var(--space-8)] py-[var(--space-3)] text-[length:var(--font-size-lg)] rounded-[var(--radius-lg)]",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  function Button(
    {
      variant = "primary",
      size = "md",
      loading = false,
      disabled,
      className = "",
      children,
      onClick,
      "data-gtm-event": gtmEvent,
      ...props
    },
    ref,
  ) {
    const { trackEvent } = useAnalytics();

    const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
      if (gtmEvent) {
        trackEvent(gtmEvent, { component: "Button", variant, label: typeof children === "string" ? children : undefined });
      }
      onClick?.(e);
    };

    return (
      <button
        ref={ref}
        className={`
          inline-flex items-center justify-center font-[var(--font-weight-semibold)]
          transition-all duration-[var(--transition-base)] cursor-pointer
          disabled:opacity-50 disabled:cursor-not-allowed
          ${variantStyles[variant]}
          ${sizeStyles[size]}
          ${className}
        `}
        disabled={disabled || loading}
        onClick={handleClick}
        data-gtm-event={gtmEvent}
        {...props}
      >
        {loading && (
          <svg
            className="mr-2 h-4 w-4 animate-spin"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
        )}
        {children}
      </button>
    );
  },
);
