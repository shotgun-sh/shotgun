import type { ReactNode } from "react";
import { ProblemCard } from "@/components/ProblemCard";
import { problems } from "@/data/problems";

/**
 * Problem section icons — inline SVGs for each pain point.
 * Simple line-based icons matching the design system.
 */
const problemIcons: Record<string, ReactNode> = {
  "context-loss": (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 6v6l4 2" />
      <path d="M4 4l16 16" strokeOpacity="0.5" />
    </svg>
  ),
  "scope-creep": (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 3l7.07 16.97 2.51-7.39 7.39-2.51L3 3z" />
      <path d="M13 13l6 6" />
    </svg>
  ),
  "rebuilding": (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
      <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
      <line x1="12" y1="22.08" x2="12" y2="12" />
    </svg>
  ),
  "no-research": (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
      <line x1="8" y1="11" x2="14" y2="11" />
    </svg>
  ),
};

export interface ProblemSectionProps {
  /** Additional CSS classes */
  className?: string;
}

/**
 * ProblemSection — "Why Complex Features Derail"
 *
 * Displays 4 problem cards in a 2x2 grid on desktop,
 * responsive to 1x2 on tablet and 1x1 on mobile.
 */
/** Fallback icon displayed when a problem ID has no matching icon */
function FallbackIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  );
}

export function ProblemSection({ className = "" }: ProblemSectionProps) {
  return (
    <div className={className}>
      {/* Section heading */}
      <div className="mb-[var(--space-12)] text-center">
        <h2
          id="problems-heading"
          className="
            text-[length:var(--font-size-3xl)] md:text-[length:var(--font-size-4xl)]
            font-[var(--font-weight-bold)]
            leading-[var(--line-height-tight)]
            tracking-[var(--letter-spacing-tight)]
            text-text-primary
          "
        >
          Why Complex Features Derail
        </h2>
      </div>

      {/* 2x2 grid: 1 col mobile, 2 cols tablet+, 2 cols desktop */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-[var(--space-6)] lg:gap-[var(--space-8)]">
        {problems.map((problem) => (
          <ProblemCard
            key={problem.id}
            icon={problemIcons[problem.id] ?? <FallbackIcon />}
            title={problem.title}
            copy={problem.copy}
          />
        ))}
      </div>
    </div>
  );
}
