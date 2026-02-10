import type { HTMLAttributes } from "react";

export interface CaseStudyBlockProps extends HTMLAttributes<HTMLDivElement> {
  /** Additional CSS classes */
  className?: string;
}

/**
 * CaseStudyBlock -- LiteLLM case study with large metric display.
 *
 * Shows "5 days vs 4 weeks" prominently with supporting narrative
 * and a research discovery callout. This is the highest-converting
 * proof point on the page.
 */
export function CaseStudyBlock({ className = "", ...props }: CaseStudyBlockProps) {
  return (
    <div
      className={`
        rounded-[var(--radius-lg)]
        border border-[var(--color-border)]
        bg-[var(--color-background)]
        overflow-hidden
        ${className}
      `}
      {...props}
    >
      {/* Main case study content */}
      <div className="p-[var(--space-8)] md:p-[var(--space-12)]">
        {/* Label */}
        <p className="
          mb-[var(--space-4)]
          text-[length:var(--font-size-sm)]
          font-[var(--font-weight-semibold)]
          uppercase tracking-[var(--letter-spacing-wide)]
          text-[var(--color-secondary)]
        ">
          Case Study
        </p>

        {/* Headline */}
        <h3 className="
          mb-[var(--space-6)]
          text-[length:var(--font-size-2xl)] md:text-[length:var(--font-size-3xl)]
          font-[var(--font-weight-bold)]
          leading-[var(--line-height-tight)]
          text-text-primary
        ">
          Research Saves Weeks
        </h3>

        {/* Narrative */}
        <div className="mb-[var(--space-8)] max-w-2xl space-y-[var(--space-3)]">
          <p className="
            text-[length:var(--font-size-base)] md:text-[length:var(--font-size-lg)]
            leading-[var(--line-height-relaxed)]
            text-[var(--color-text-secondary)]
          ">
            We needed usage-based billing for LLM calls. Our first instinct? Build a custom proxy.
            Every AI coding agent we asked (Cursor, Claude Code, Copilot) suggested the same thing.
          </p>
          <p className="
            text-[length:var(--font-size-base)] md:text-[length:var(--font-size-lg)]
            leading-[var(--line-height-relaxed)]
            text-[var(--color-text-secondary)]
          ">
            Then we ran Shotgun&apos;s research phase. In 30 minutes, it discovered LiteLLM
            Proxy&mdash;a mature, battle-tested solution for exactly this problem.
          </p>
        </div>

        {/* Large metric display */}
        <div className="
          mb-[var(--space-8)]
          flex flex-col items-start gap-[var(--space-2)]
        ">
          <div className="flex items-baseline gap-[var(--space-3)] flex-wrap">
            <span className="
              text-[length:var(--font-size-5xl)] md:text-[length:var(--font-size-6xl)]
              font-[var(--font-weight-bold)]
              leading-[1]
              text-[var(--color-accent)]
            ">
              5 days
            </span>
            <span className="
              text-[length:var(--font-size-2xl)] md:text-[length:var(--font-size-3xl)]
              font-[var(--font-weight-medium)]
              text-[var(--color-text-muted)]
            ">
              vs
            </span>
            <span className="
              text-[length:var(--font-size-5xl)] md:text-[length:var(--font-size-6xl)]
              font-[var(--font-weight-bold)]
              leading-[1]
              text-text-primary
              line-through decoration-[var(--color-text-muted)] decoration-2
            ">
              4 weeks
            </span>
          </div>
          <p className="
            text-[length:var(--font-size-sm)]
            text-[var(--color-text-muted)]
          ">
            Research phase found existing solution
          </p>
        </div>

        {/* CTA question */}
        <p className="
          text-[length:var(--font-size-lg)] md:text-[length:var(--font-size-xl)]
          font-[var(--font-weight-semibold)]
          text-text-primary
        ">
          What could you ship 3 weeks faster?
        </p>
      </div>

      {/* Research discovery callout */}
      <div className="
        border-t border-[var(--color-border)]
        bg-[var(--color-surface)]
        px-[var(--space-8)] md:px-[var(--space-12)]
        py-[var(--space-5)]
        flex items-start gap-[var(--space-3)]
      ">
        {/* Light bulb icon */}
        <div className="mt-[2px] shrink-0 text-[var(--color-secondary)]">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <line x1="9" y1="18" x2="15" y2="18" />
            <line x1="10" y1="22" x2="14" y2="22" />
            <path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1 .23 2.23 1.5 3.5A4.61 4.61 0 0 1 8.91 14" />
          </svg>
        </div>
        <p className="
          text-[length:var(--font-size-sm)]
          leading-[var(--line-height-relaxed)]
          text-[var(--color-text-secondary)]
        ">
          <span className="font-[var(--font-weight-semibold)] text-text-primary">Research discovery:</span>{" "}
          Shotgun&apos;s research phase found LiteLLM Proxy in under 30 minutes. Without research,
          the team would have spent 4 weeks building custom infrastructure that already existed.
        </p>
      </div>
    </div>
  );
}
