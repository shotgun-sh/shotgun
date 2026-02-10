import type { HTMLAttributes, ReactNode } from "react";

export interface FeatureRowProps extends HTMLAttributes<HTMLElement> {
  /** Icon element (32px recommended) */
  icon: ReactNode;
  /** Feature title (bold) */
  title: string;
  /** One-line benefit (regular weight) */
  benefit: string;
}

/**
 * FeatureRow — horizontal row with icon, title, and benefit.
 *
 * Displays inline on desktop (icon + title + benefit in a single row).
 * Stacks cleanly on mobile with title and benefit below the icon.
 */
export function FeatureRow({
  icon,
  title,
  benefit,
  className = "",
  ...props
}: FeatureRowProps) {
  return (
    <div
      className={`
        flex items-start gap-[var(--space-4)]
        py-[var(--space-4)]
        border-b border-border-light last:border-b-0
        ${className}
      `}
      {...props}
    >
      {/* Icon — 32px container */}
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--radius-sm)] bg-accent-blue-50 text-accent-blue-600">
        {icon}
      </div>

      {/* Title + Benefit — horizontal on desktop, stacked on mobile */}
      <div className="flex flex-col sm:flex-row sm:items-baseline sm:gap-[var(--space-2)] min-w-0">
        <h3
          className="
            text-[length:var(--font-size-base)] lg:text-[length:var(--font-size-lg)]
            font-[var(--font-weight-semibold)]
            leading-[var(--line-height-snug)]
            text-text-primary
            shrink-0
            m-0
          "
        >
          {title}
        </h3>
        <span className="hidden sm:inline text-text-muted" aria-hidden="true">
          —
        </span>
        <span
          className="
            text-[length:var(--font-size-sm)] sm:text-[length:var(--font-size-base)]
            leading-[var(--line-height-relaxed)]
            text-text-secondary
          "
        >
          {benefit}
        </span>
      </div>
    </div>
  );
}
