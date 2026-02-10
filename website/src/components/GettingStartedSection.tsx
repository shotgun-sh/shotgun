import type { ReactNode } from "react";
import { OnboardingStep } from "@/components/OnboardingStep";
import { CodeBlock } from "@/components/CodeBlock";
import { onboardingSteps } from "@/data/onboarding";

/**
 * Onboarding step icons -- inline SVGs matching the design system.
 */
const stepIcons: Record<string, ReactNode> = {
  install: (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="4 17 10 11 4 5" />
      <line x1="12" y1="19" x2="20" y2="19" />
    </svg>
  ),
  "api-key": (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="m21 2-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0 3 3L22 7l-3-3m-3.5 3.5L19 4" />
    </svg>
  ),
  analyze: (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z" />
      <path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z" />
      <path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0" />
      <path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5" />
    </svg>
  ),
};

export interface GettingStartedSectionProps {
  /** Additional CSS classes */
  className?: string;
}

/**
 * GettingStartedSection -- "Get Started Free"
 *
 * 3-step onboarding guide with code block for install command
 * and trust signals below. Removes all barriers to trying Shotgun.
 */
export function GettingStartedSection({ className = "" }: GettingStartedSectionProps) {
  return (
    <div className={className}>
      {/* Section heading */}
      <div className="mb-[var(--space-10)] text-center">
        <h2
          id="getting-started-heading"
          className="
            mb-[var(--space-3)]
            text-[length:var(--font-size-3xl)] md:text-[length:var(--font-size-4xl)]
            font-[var(--font-weight-bold)]
            leading-[var(--line-height-tight)]
            tracking-[var(--letter-spacing-tight)]
            text-text-primary
          "
        >
          Get Started Free
        </h2>
        <p className="
          text-[length:var(--font-size-lg)] md:text-[length:var(--font-size-xl)]
          text-[var(--color-text-secondary)]
        ">
          3 steps to your first spec
        </p>
      </div>

      {/* Onboarding steps -- row on desktop, vertical on mobile */}
      <div className="
        mb-[var(--space-12)]
        flex flex-col lg:flex-row
        gap-[var(--space-8)] lg:gap-[var(--space-6)]
        items-start lg:items-stretch
      ">
        {/* Connector lines on desktop */}
        {onboardingSteps.map((step, index) => (
          <div key={step.id} className="flex flex-col lg:flex-row items-center lg:flex-1">
            <OnboardingStep
              number={step.number}
              icon={stepIcons[step.id] ?? null}
              title={step.title}
              description={step.description}
            />
            {/* Arrow connector between steps (desktop only) */}
            {index < onboardingSteps.length - 1 && (
              <div className="
                hidden lg:flex
                items-center justify-center
                shrink-0
                px-[var(--space-2)]
                text-[var(--color-gray-300)]
              ">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <polyline points="9 18 15 12 9 6" />
                </svg>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Install command code block */}
      <div className="mx-auto max-w-lg mb-[var(--space-10)]">
        <CodeBlock
          code="uvx shotgun-sh@latest"
          language="bash"
          showPrompt={true}
          showCopyButton={true}
          data-gtm-event="getting_started_code_copy"
        />
      </div>

      {/* Trust signals */}
      <div className="
        mx-auto max-w-2xl
        grid grid-cols-1 sm:grid-cols-2 gap-[var(--space-3)]
      ">
        {[
          "No credit card required",
          "Free tier for personal projects",
          "$10 = $10 usage",
          "Works locally or cloud",
          "Open source research agent",
        ].map((signal) => (
          <div
            key={signal}
            className="
              flex items-center gap-[var(--space-2)]
              text-[length:var(--font-size-sm)]
              text-[var(--color-text-secondary)]
            "
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--color-success)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="shrink-0">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            {signal}
          </div>
        ))}
      </div>
    </div>
  );
}
