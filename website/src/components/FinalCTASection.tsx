"use client";

import { HeroButton } from "@/components/HeroButton";
import { useAnalytics } from "@/hooks/useAnalytics";

export interface FinalCTASectionProps {
  /** Additional CSS classes */
  className?: string;
}

/**
 * FinalCTASection -- "Ready to Ship Faster?"
 *
 * Closing call-to-action with large primary CTA button,
 * secondary text links (comparison article, case study),
 * and benefit reminder paragraph.
 */
export function FinalCTASection({ className = "" }: FinalCTASectionProps) {
  const { trackEvent } = useAnalytics();

  return (
    <div className={`text-center ${className}`}>
      {/* Section heading */}
      <h2
        id="final-cta-heading"
        className="
          mb-[var(--space-4)]
          text-[length:var(--font-size-3xl)] md:text-[length:var(--font-size-5xl)]
          font-[var(--font-weight-bold)]
          leading-[var(--line-height-tight)]
          tracking-[var(--letter-spacing-tight)]
          text-text-inverse
        "
      >
        Ready to Ship Faster?
      </h2>

      {/* Subheading */}
      <p className="
        mb-[var(--space-10)]
        mx-auto max-w-2xl
        text-[length:var(--font-size-lg)] md:text-[length:var(--font-size-xl)]
        leading-[var(--line-height-relaxed)]
        text-[var(--color-gray-300)]
      ">
        Stop losing context on complex features. Shotgun keeps your AI agent on track.
        Research before building. Specs that understand your codebase. Export to any tool.
      </p>

      {/* Primary CTA button */}
      <div className="mb-[var(--space-8)]">
        <HeroButton
          data-gtm-event="final_cta_signup"
        >
          Start Free with BYOK
        </HeroButton>
      </div>

      {/* Secondary CTAs */}
      <div className="
        mb-[var(--space-10)]
        flex flex-col sm:flex-row items-center justify-center
        gap-[var(--space-4)]
      ">
        <a
          href="#comparison"
          className="
            text-[length:var(--font-size-base)]
            font-[var(--font-weight-medium)]
            text-[var(--color-gray-300)]
            underline underline-offset-4 decoration-[var(--color-gray-500)]
            hover:text-text-inverse hover:decoration-text-inverse
            transition-colors duration-[var(--transition-fast)]
          "
          data-gtm-event="final_cta_comparison"
          onClick={() =>
            trackEvent("final_cta_comparison", {
              component: "FinalCTASection",
              label: "Shotgun vs Spec Kit comparison",
            })
          }
        >
          See the Shotgun vs Spec Kit comparison
        </a>
        <span className="hidden sm:inline text-[var(--color-gray-500)]" aria-hidden="true">&middot;</span>
        <a
          href="#social-proof"
          className="
            text-[length:var(--font-size-base)]
            font-[var(--font-weight-medium)]
            text-[var(--color-gray-300)]
            underline underline-offset-4 decoration-[var(--color-gray-500)]
            hover:text-text-inverse hover:decoration-text-inverse
            transition-colors duration-[var(--transition-fast)]
          "
          data-gtm-event="final_cta_case_study"
          onClick={() =>
            trackEvent("final_cta_case_study", {
              component: "FinalCTASection",
              label: "LiteLLM research case study",
            })
          }
        >
          How we saved 3 weeks with LiteLLM research
        </a>
      </div>

      {/* Benefit reminder paragraph */}
      <div className="
        mx-auto max-w-2xl
        text-[length:var(--font-size-base)]
        leading-[var(--line-height-relaxed)]
        text-[var(--color-gray-400)]
      ">
        <p>
          Shotgun researches before you build. Your specs understand your codebase.
          Multi-agent orchestration keeps complexity manageable. Export to Cursor,
          Claude Code, Windsurf, or any AI tool you choose.
        </p>
        <p className="mt-[var(--space-3)] font-[var(--font-weight-semibold)] text-[var(--color-gray-300)]">
          Start free. No credit card. One command:{" "}
          <code className="
            font-mono
            text-[var(--color-accent)]
            bg-[var(--color-gray-800)]
            px-[var(--space-2)] py-[var(--space-1)]
            rounded-[var(--radius-sm)]
          ">
            uvx shotgun-sh@latest
          </code>
        </p>
      </div>
    </div>
  );
}
