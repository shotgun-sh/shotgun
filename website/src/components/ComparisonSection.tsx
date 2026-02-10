import { ComparisonTable } from "@/components/ComparisonTable";

export interface ComparisonSectionProps {
  /** Additional CSS classes */
  className?: string;
}

/**
 * ComparisonSection — "Intelligence vs Templates"
 *
 * Positions Shotgun vs Spec Kit with section heading, subheading,
 * full comparison table, and key insight callout.
 */
export function ComparisonSection({ className = "" }: ComparisonSectionProps) {
  return (
    <div className={className}>
      {/* Section heading */}
      <div className="mb-[var(--space-12)] text-center">
        <h2
          id="comparison-heading"
          className="
            text-[length:var(--font-size-3xl)] md:text-[length:var(--font-size-4xl)]
            font-[var(--font-weight-bold)]
            leading-[var(--line-height-tight)]
            tracking-[var(--letter-spacing-tight)]
            text-text-primary
            mb-[var(--space-4)]
          "
        >
          Intelligence vs Templates
        </h2>
        <p
          className="
            text-[length:var(--font-size-lg)] md:text-[length:var(--font-size-xl)]
            leading-[var(--line-height-relaxed)]
            text-text-secondary
            max-w-2xl mx-auto
          "
        >
          Why developers switch from Spec Kit to Shotgun
        </p>
      </div>

      {/* Comparison Table */}
      <ComparisonTable className="mb-[var(--space-12)]" />

      {/* Key Insight Callout */}
      <div
        className="
          mx-auto max-w-2xl
          rounded-[var(--radius-lg)]
          border-l-4 border-accent-blue-500
          bg-accent-blue-50
          p-[var(--space-6)] md:p-[var(--space-8)]
        "
      >
        <p
          className="
            text-[length:var(--font-size-xl)] md:text-[length:var(--font-size-2xl)]
            font-[var(--font-weight-bold)]
            leading-[var(--line-height-snug)]
            text-text-primary
            mb-[var(--space-4)]
          "
        >
          The difference isn&apos;t features. It&apos;s thinking.
        </p>
        <p
          className="
            text-[length:var(--font-size-base)] md:text-[length:var(--font-size-lg)]
            leading-[var(--line-height-relaxed)]
            text-text-secondary
          "
        >
          Spec Kit provides structure: &ldquo;Here&rsquo;s how to organize a spec.&rdquo;
          Shotgun provides intelligence: &ldquo;Here&rsquo;s what your spec should be, based on your codebase and research.&rdquo;
        </p>
      </div>
    </div>
  );
}
