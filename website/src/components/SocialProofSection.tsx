import { CaseStudyBlock } from "@/components/CaseStudyBlock";

export interface SocialProofSectionProps {
  /** Additional CSS classes */
  className?: string;
}

/**
 * SocialProofSection -- "Why Developers Choose Shotgun"
 *
 * Combines the LiteLLM case study block with a competitive scoring
 * comparison (Shotgun 48/50 vs Spec Kit 31/50) to build credibility
 * and drive conversion.
 */
export function SocialProofSection({ className = "" }: SocialProofSectionProps) {
  return (
    <div className={className}>
      {/* Section heading */}
      <div className="mb-[var(--space-10)] text-center">
        <h2
          id="social-proof-heading"
          className="
            text-[length:var(--font-size-3xl)] md:text-[length:var(--font-size-4xl)]
            font-[var(--font-weight-bold)]
            leading-[var(--line-height-tight)]
            tracking-[var(--letter-spacing-tight)]
            text-text-primary
          "
        >
          Why Developers Choose Shotgun
        </h2>
      </div>

      {/* Two-column layout on desktop: case study + scoring */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-[var(--space-8)]">
        {/* Case study block -- takes 3/5 of the width */}
        <div className="lg:col-span-3">
          <CaseStudyBlock />
        </div>

        {/* Competitive scoring comparison -- takes 2/5 of the width */}
        <div className="lg:col-span-2 flex flex-col gap-[var(--space-6)]">
          {/* Scoring comparison card */}
          <div className="
            rounded-[var(--radius-lg)]
            border border-[var(--color-border)]
            bg-[var(--color-background)]
            p-[var(--space-8)]
            flex-1
          ">
            <p className="
              mb-[var(--space-4)]
              text-[length:var(--font-size-sm)]
              font-[var(--font-weight-semibold)]
              uppercase tracking-[var(--letter-spacing-wide)]
              text-[var(--color-secondary)]
            ">
              Built for Spec-Driven Development
            </p>

            {/* Shotgun score */}
            <div className="mb-[var(--space-6)]">
              <div className="flex items-baseline gap-[var(--space-2)] mb-[var(--space-2)]">
                <span className="
                  text-[length:var(--font-size-4xl)] md:text-[length:var(--font-size-5xl)]
                  font-[var(--font-weight-bold)]
                  leading-[1]
                  text-[var(--color-accent)]
                ">
                  48
                </span>
                <span className="
                  text-[length:var(--font-size-xl)]
                  font-[var(--font-weight-medium)]
                  text-[var(--color-text-muted)]
                ">
                  /50
                </span>
              </div>
              <p className="
                text-[length:var(--font-size-base)]
                font-[var(--font-weight-semibold)]
                text-text-primary
              ">
                Shotgun
              </p>
              {/* Score bar */}
              <div className="mt-[var(--space-2)] h-2 w-full rounded-full bg-[var(--color-gray-200)]">
                <div
                  className="h-full rounded-full bg-[var(--color-accent)] transition-all duration-700"
                  style={{ width: "96%" }}
                />
              </div>
            </div>

            {/* Spec Kit score */}
            <div className="mb-[var(--space-6)]">
              <div className="flex items-baseline gap-[var(--space-2)] mb-[var(--space-2)]">
                <span className="
                  text-[length:var(--font-size-4xl)] md:text-[length:var(--font-size-5xl)]
                  font-[var(--font-weight-bold)]
                  leading-[1]
                  text-[var(--color-text-muted)]
                ">
                  31
                </span>
                <span className="
                  text-[length:var(--font-size-xl)]
                  font-[var(--font-weight-medium)]
                  text-[var(--color-text-muted)]
                ">
                  /50
                </span>
              </div>
              <p className="
                text-[length:var(--font-size-base)]
                font-[var(--font-weight-semibold)]
                text-[var(--color-text-secondary)]
              ">
                Spec Kit
              </p>
              {/* Score bar */}
              <div className="mt-[var(--space-2)] h-2 w-full rounded-full bg-[var(--color-gray-200)]">
                <div
                  className="h-full rounded-full bg-[var(--color-gray-400)] transition-all duration-700"
                  style={{ width: "62%" }}
                />
              </div>
            </div>

            {/* Supporting copy */}
            <p className="
              text-[length:var(--font-size-sm)]
              leading-[var(--line-height-relaxed)]
              text-[var(--color-text-secondary)]
            ">
              Evaluated across 10 decision factors: codebase understanding, research capability,
              structured workflow, multi-agent architecture, export flexibility, PR staging,
              team collaboration, LLM provider flexibility, ease of setup, and cost efficiency.
            </p>
          </div>

          {/* Key differentiators card */}
          <div className="
            rounded-[var(--radius-lg)]
            border border-[var(--color-border)]
            bg-[var(--color-background)]
            p-[var(--space-6)]
          ">
            <p className="
              mb-[var(--space-4)]
              text-[length:var(--font-size-sm)]
              font-[var(--font-weight-semibold)]
              text-text-primary
            ">
              Top differentiators
            </p>

            <div className="space-y-[var(--space-3)]">
              {[
                "Codebase Understanding",
                "Research Capability",
                "Multi-Agent Architecture",
              ].map((label) => (
                <div key={label} className="flex items-center gap-[var(--space-3)]">
                  <span className="
                    inline-flex items-center justify-center
                    w-5 h-5 rounded-full
                    bg-[var(--color-success)] text-white
                    shrink-0
                  ">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  </span>
                  <span className="
                    text-[length:var(--font-size-sm)]
                    text-text-primary
                  ">
                    {label}
                  </span>
                  <span className="
                    ml-auto
                    inline-flex items-center justify-center
                    w-5 h-5 rounded-full
                    bg-[var(--color-gray-200)] text-[var(--color-gray-400)]
                    shrink-0
                  ">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <line x1="18" y1="6" x2="6" y2="18" />
                      <line x1="6" y1="6" x2="18" y2="18" />
                    </svg>
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
