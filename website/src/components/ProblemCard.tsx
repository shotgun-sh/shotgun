import type { HTMLAttributes, ReactNode } from "react";

export interface ProblemCardProps extends HTMLAttributes<HTMLDivElement> {
  /** Icon element to display in the card header */
  icon: ReactNode;
  /** Problem title */
  title: string;
  /** Problem description copy */
  copy: string;
}

/**
 * ProblemCard — reusable card component for the Problem section.
 *
 * Displays an icon, title, and description copy with consistent spacing
 * and a subtle hover state. Styled to match the Card component patterns
 * with navy/dark theme compatibility.
 */
export function ProblemCard({
  icon,
  title,
  copy,
  className = "",
  ...props
}: ProblemCardProps) {
  return (
    <div
      className={`
        rounded-[var(--radius-lg)]
        border border-border-light
        bg-surface-elevated
        p-[var(--space-6)] lg:p-[var(--space-8)]
        transition-all duration-[var(--transition-base)]
        hover:shadow-[var(--shadow-lg)] hover:-translate-y-0.5
        hover:border-accent-orange-200
        ${className}
      `}
      {...props}
    >
      {/* Icon */}
      <div className="mb-[var(--space-4)] flex h-12 w-12 items-center justify-center rounded-[var(--radius-md)] bg-accent-orange-50 text-accent-orange-600">
        {icon}
      </div>

      {/* Title */}
      <h3
        className="
          mb-[var(--space-3)]
          text-[length:var(--font-size-lg)]
          font-[var(--font-weight-semibold)]
          leading-[var(--line-height-snug)]
          text-text-primary
        "
      >
        {title}
      </h3>

      {/* Copy */}
      <p
        className="
          text-[length:var(--font-size-base)]
          leading-[var(--line-height-relaxed)]
          text-text-secondary
        "
      >
        {copy}
      </p>
    </div>
  );
}
