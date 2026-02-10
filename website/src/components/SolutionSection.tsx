import type { ReactNode } from "react";
import { SolutionCard } from "@/components/SolutionCard";
import { solutions } from "@/data/solutions";

/**
 * Solution section icons — inline SVGs mirroring problem icons.
 * Complementary line-based icons matching the design system.
 */
const solutionIcons: Record<string, ReactNode> = {
  "persistent-understanding": (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <ellipse cx="12" cy="5" rx="9" ry="3" />
      <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
      <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
    </svg>
  ),
  "research-first": (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
      <line x1="11" y1="8" x2="11" y2="14" />
      <line x1="8" y1="11" x2="14" y2="11" />
    </svg>
  ),
  "multi-stage": (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="8" y1="6" x2="21" y2="6" />
      <line x1="8" y1="12" x2="21" y2="12" />
      <line x1="8" y1="18" x2="21" y2="18" />
      <line x1="3" y1="6" x2="3.01" y2="6" />
      <line x1="3" y1="12" x2="3.01" y2="12" />
      <line x1="3" y1="18" x2="3.01" y2="18" />
    </svg>
  ),
  "agent-orchestration": (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  ),
};

export interface SolutionSectionProps {
  /** Additional CSS classes */
  className?: string;
}

/**
 * SolutionSection — "How Shotgun Works"
 *
 * Mirrors the ProblemSection layout with 4 solution cards
 * in a 2x2 grid on desktop, responsive to smaller breakpoints.
 * Includes section heading and overview copy.
 */
/** Fallback icon displayed when a solution ID has no matching icon */
function FallbackIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  );
}

export function SolutionSection({ className = "" }: SolutionSectionProps) {
  return (
    <div className={className}>
      {/* Section heading */}
      <div className="mb-[var(--space-12)] text-center">
        <h2
          id="solutions-heading"
          className="
            text-[length:var(--font-size-3xl)] md:text-[length:var(--font-size-4xl)]
            font-[var(--font-weight-bold)]
            leading-[var(--line-height-tight)]
            tracking-[var(--letter-spacing-tight)]
            text-text-primary
          "
        >
          How Shotgun Works
        </h2>

        {/* Overview copy */}
        <p
          className="
            mt-[var(--space-4)]
            mx-auto max-w-3xl
            text-[length:var(--font-size-base)] md:text-[length:var(--font-size-lg)]
            leading-[var(--line-height-relaxed)]
            text-text-secondary
          "
        >
          Shotgun analyzes your codebase, researches existing solutions, and
          generates specs that keep your AI agent on track&mdash;across multiple
          sessions, multiple features, multiple team members.
        </p>
      </div>

      {/* 2x2 grid: 1 col mobile, 2 cols tablet+, 2 cols desktop */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-[var(--space-6)] lg:gap-[var(--space-8)]">
        {solutions.map((solution) => (
          <SolutionCard
            key={solution.id}
            icon={solutionIcons[solution.id] ?? <FallbackIcon />}
            title={solution.title}
            benefit={solution.benefit}
            copy={solution.copy}
          />
        ))}
      </div>
    </div>
  );
}
