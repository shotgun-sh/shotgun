import type { HTMLAttributes, ReactNode } from "react";

export interface SolutionCardProps extends HTMLAttributes<HTMLElement> {
  /** Icon element to display in the card header */
  icon: ReactNode;
  /** Solution title */
  title: string;
  /** Bold benefit statement */
  benefit: string;
  /** Detailed description copy */
  copy: string;
}

/**
 * SolutionCard — card component for the Solution section.
 *
 * Mirrors ProblemCard layout with an additional benefit statement.
 * Includes icon, title, bold benefit, and detailed copy with
 * consistent spacing and hover state matching problem cards.
 */
export function SolutionCard({
  icon,
  title,
  benefit,
  copy,
  className = "",
  ...props
}: SolutionCardProps) {
  return (
    <article
      className={`
        rounded-[var(--radius-lg)]
        border border-border-light
        bg-surface-elevated
        p-[var(--space-6)] lg:p-[var(--space-8)]
        transition-all duration-[var(--transition-base)]
        hover:shadow-[var(--shadow-lg)] hover:-translate-y-0.5
        hover:border-accent-blue-200
        ${className}
      `}
      {...props}
    >
      {/* Icon */}
      <div className="mb-[var(--space-4)] flex h-12 w-12 items-center justify-center rounded-[var(--radius-md)] bg-accent-blue-50 text-accent-blue-600">
        {icon}
      </div>

      {/* Title */}
      <h3
        className="
          mb-[var(--space-2)]
          text-[length:var(--font-size-lg)]
          font-[var(--font-weight-semibold)]
          leading-[var(--line-height-snug)]
          text-text-primary
        "
      >
        {title}
      </h3>

      {/* Benefit statement */}
      <p
        className="
          mb-[var(--space-3)]
          text-[length:var(--font-size-base)]
          font-[var(--font-weight-medium)]
          leading-[var(--line-height-normal)]
          text-accent-blue-700
        "
      >
        {benefit}
      </p>

      {/* Detailed copy */}
      <p
        className="
          text-[length:var(--font-size-base)]
          leading-[var(--line-height-relaxed)]
          text-text-secondary
        "
      >
        {copy}
      </p>
    </article>
  );
}
