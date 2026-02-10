import type { HTMLAttributes, ReactNode } from "react";

export interface OnboardingStepProps extends HTMLAttributes<HTMLDivElement> {
  /** Step number (1, 2, 3) */
  number: number;
  /** Icon element to display */
  icon: ReactNode;
  /** Step title */
  title: string;
  /** Step description */
  description: string;
  /** Additional CSS classes */
  className?: string;
}

/**
 * OnboardingStep -- individual step in the Getting Started flow.
 *
 * Displays step number, icon, title, and description.
 * Row layout on desktop, vertical stack on mobile.
 */
export function OnboardingStep({
  number,
  icon,
  title,
  description,
  className = "",
  ...props
}: OnboardingStepProps) {
  return (
    <div
      className={`
        flex flex-col items-center text-center
        lg:flex-1
        ${className}
      `}
      {...props}
    >
      {/* Step number badge */}
      <div className="
        mb-[var(--space-4)]
        flex items-center justify-center
        w-10 h-10 rounded-full
        bg-[var(--color-accent)] text-text-inverse
        text-[length:var(--font-size-lg)]
        font-[var(--font-weight-bold)]
      ">
        {number}
      </div>

      {/* Icon */}
      <div className="
        mb-[var(--space-3)]
        flex items-center justify-center
        w-12 h-12 rounded-[var(--radius-lg)]
        bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]
      ">
        {icon}
      </div>

      {/* Title */}
      <h3 className="
        mb-[var(--space-2)]
        text-[length:var(--font-size-lg)] md:text-[length:var(--font-size-xl)]
        font-[var(--font-weight-bold)]
        leading-[var(--line-height-tight)]
        text-text-primary
      ">
        {title}
      </h3>

      {/* Description */}
      <p className="
        max-w-xs
        text-[length:var(--font-size-sm)] md:text-[length:var(--font-size-base)]
        leading-[var(--line-height-relaxed)]
        text-[var(--color-text-secondary)]
      ">
        {description}
      </p>
    </div>
  );
}
