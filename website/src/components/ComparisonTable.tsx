import { comparisonRows } from "@/data/comparison";

export interface ComparisonTableProps {
  /** Additional CSS classes */
  className?: string;
}

/**
 * ComparisonTable — Shotgun vs Spec Kit comparison table.
 *
 * Displays 10+ rows of decision factors with visual emphasis
 * on Shotgun advantages. Scrollable on mobile, full table on desktop.
 * Each row includes data-gtm attributes for tracking.
 */
export function ComparisonTable({ className = "" }: ComparisonTableProps) {
  return (
    <div className={`overflow-x-auto -mx-[var(--space-4)] px-[var(--space-4)] md:mx-0 md:px-0 ${className}`}>
      <table
        className="
          w-full min-w-[600px] md:min-w-0
          border-collapse
          text-[length:var(--font-size-sm)] md:text-[length:var(--font-size-base)]
        "
        role="table"
        aria-label="Shotgun vs Spec Kit comparison"
      >
        <thead>
          <tr className="border-b-2 border-border">
            <th
              className="
                py-[var(--space-3)] md:py-[var(--space-4)]
                pr-[var(--space-4)]
                text-left
                text-[length:var(--font-size-sm)] md:text-[length:var(--font-size-base)]
                font-[var(--font-weight-semibold)]
                text-text-muted
                uppercase tracking-[var(--letter-spacing-wide)]
                w-[30%]
              "
            >
              Aspect
            </th>
            <th
              className="
                py-[var(--space-3)] md:py-[var(--space-4)]
                px-[var(--space-4)]
                text-left
                text-[length:var(--font-size-sm)] md:text-[length:var(--font-size-base)]
                font-[var(--font-weight-bold)]
                text-accent-blue-700
                w-[35%]
              "
            >
              <span className="flex items-center gap-[var(--space-2)]">
                <span className="inline-block h-2.5 w-2.5 rounded-full bg-accent-blue-500" aria-hidden="true" />
                Shotgun
              </span>
            </th>
            <th
              className="
                py-[var(--space-3)] md:py-[var(--space-4)]
                pl-[var(--space-4)]
                text-left
                text-[length:var(--font-size-sm)] md:text-[length:var(--font-size-base)]
                font-[var(--font-weight-semibold)]
                text-text-secondary
                w-[35%]
              "
            >
              Spec Kit
            </th>
          </tr>
        </thead>
        <tbody>
          {comparisonRows.map((row) => (
            <tr
              key={row.id}
              className="
                border-b border-border-light
                transition-colors duration-[var(--transition-fast)]
                hover:bg-surface-elevated
              "
              data-gtm-comparison={row.id}
            >
              {/* Aspect */}
              <td
                className="
                  py-[var(--space-3)] md:py-[var(--space-4)]
                  pr-[var(--space-4)]
                  font-[var(--font-weight-medium)]
                  text-text-primary
                  align-top
                "
              >
                {row.aspect}
              </td>

              {/* Shotgun */}
              <td
                className={`
                  py-[var(--space-3)] md:py-[var(--space-4)]
                  px-[var(--space-4)]
                  align-top
                  ${
                    row.shotgunAdvantage
                      ? "text-text-primary font-[var(--font-weight-medium)]"
                      : "text-text-secondary"
                  }
                `}
              >
                <span className="flex items-start gap-[var(--space-2)]">
                  {row.shotgunAdvantage && (
                    <span className="mt-0.5 shrink-0 text-[var(--color-success)]" role="img" aria-label="Shotgun advantage">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    </span>
                  )}
                  <span>{row.shotgun}</span>
                </span>
              </td>

              {/* Spec Kit */}
              <td
                className="
                  py-[var(--space-3)] md:py-[var(--space-4)]
                  pl-[var(--space-4)]
                  text-text-muted
                  align-top
                "
              >
                {row.specKit}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
