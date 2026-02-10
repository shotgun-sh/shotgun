import { HeroButton } from "@/components/HeroButton";
import { CodeBlock } from "@/components/CodeBlock";
import { HeroImage } from "@/components/HeroImage";

export interface HeroProps {
  /** Optional hero image source */
  heroImageSrc?: string;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Hero section component for the Shotgun landing page.
 *
 * Includes:
 * - Large headline with responsive typography (48px desktop, 32px mobile)
 * - Subheading with problem reframe + solution hint
 * - Primary CTA button ("Start Free with BYOK")
 * - Secondary CTA code block (uvx shotgun-sh@latest)
 * - Trust signal text
 * - Hero visual placeholder
 *
 * All copy matches specification.md Option A (Intelligence Angle).
 */
export function Hero({ heroImageSrc, className = "" }: HeroProps) {
  return (
    <div className={className}>
      {/* Content layout: two-column on desktop, stacked on mobile */}
      <div className="flex flex-col gap-[var(--space-12)] lg:flex-row lg:items-center lg:gap-[var(--space-16)]">
        {/* Left column: Text content + CTAs */}
        <div className="flex-1 lg:max-w-[55%]">
          {/* Headline */}
          <h1
            className="
              text-[length:2rem] md:text-[length:var(--font-size-5xl)]
              font-[var(--font-weight-bold)]
              leading-[var(--line-height-tight)]
              tracking-[var(--letter-spacing-tight)]
              text-text-inverse
            "
          >
            Intelligent Specs, Not Templates.{" "}
            <span className="text-accent-orange-300">
              Your Codebase Understanding.
            </span>
          </h1>

          {/* Subheading */}
          <p
            className="
              mt-[var(--space-6)]
              text-[length:var(--font-size-base)] md:text-[length:var(--font-size-xl)]
              font-[var(--font-weight-medium)]
              leading-[var(--line-height-relaxed)]
              text-navy-200
            "
          >
            Where Spec Kit gives you a blank template, Shotgun analyzes your
            codebase, researches existing solutions, and generates contextual
            specs. Persistent. Intelligent. Research-first.
          </p>

          {/* CTAs: Button + Code Block */}
          <div className="mt-[var(--space-8)] flex flex-col gap-[var(--space-4)] sm:flex-row sm:items-center">
            <HeroButton data-gtm-event="hero_cta_signup" />
            <div className="sm:min-w-[280px]">
              <CodeBlock
                code="uvx shotgun-sh@latest"
                language="bash"
                showLineNumbers={false}
                data-gtm-event="hero_code_copy"
              />
            </div>
          </div>

          {/* Trust signal */}
          <p
            className="
              mt-[var(--space-4)]
              text-[length:var(--font-size-sm)] md:text-[length:var(--font-size-base)]
              text-navy-300
              leading-[var(--line-height-normal)]
            "
          >
            No credit card. $10 = $10 usage. Works with Cursor, Claude Code,
            Windsurf, and more.
          </p>
        </div>

        {/* Right column: Hero visual */}
        <div className="flex-1 lg:max-w-[45%]">
          <HeroImage
            src={heroImageSrc}
            alt="Shotgun dashboard showing intelligent spec generation workflow with codebase analysis, research, and multi-stage task export"
            aspectRatio="16:9"
          />
        </div>
      </div>
    </div>
  );
}
