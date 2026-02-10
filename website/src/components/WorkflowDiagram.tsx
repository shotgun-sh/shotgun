export interface WorkflowDiagramProps {
  /** Additional CSS classes */
  className?: string;
}

/**
 * WorkflowDiagram — visual showing Research -> Spec -> Plan -> Tasks -> Export
 *
 * A clean SVG-based workflow diagram rendered inline for maximum
 * performance and accessibility. Responsive layout stacks on mobile.
 */

interface StepData {
  label: string;
  sublabel: string;
}

const steps: StepData[] = [
  { label: "Research", sublabel: "Discover Solutions" },
  { label: "Specifications", sublabel: "Structure Requirements" },
  { label: "Planning", sublabel: "Stage Execution" },
  { label: "Tasks", sublabel: "Ready for AI Tools" },
  { label: "Export", sublabel: "Ship to Your Editor" },
];

export function WorkflowDiagram({ className = "" }: WorkflowDiagramProps) {
  return (
    <div className={className}>
      {/* Caption */}
      <p
        className="
          mb-[var(--space-6)]
          text-center
          text-[length:var(--font-size-sm)] md:text-[length:var(--font-size-base)]
          font-[var(--font-weight-medium)]
          text-text-secondary
        "
      >
        5-stage workflow. Research before you build. Structure before you plan.
        Checkpoints to review and adjust.
      </p>

      {/* Desktop/tablet: horizontal flow */}
      <div className="hidden md:flex items-center justify-center gap-[var(--space-2)]">
        {steps.map((step, index) => (
          <div key={step.label} className="flex items-center">
            {/* Step box */}
            <div
              className="
                flex flex-col items-center justify-center
                rounded-[var(--radius-lg)]
                border border-accent-blue-200
                bg-accent-blue-50
                px-[var(--space-4)] lg:px-[var(--space-6)]
                py-[var(--space-3)] lg:py-[var(--space-4)]
                min-w-[120px] lg:min-w-[140px]
                text-center
                transition-all duration-[var(--transition-base)]
                hover:shadow-[var(--shadow-md)] hover:border-accent-blue-400
              "
            >
              <span
                className="
                  text-[length:var(--font-size-sm)] lg:text-[length:var(--font-size-base)]
                  font-[var(--font-weight-semibold)]
                  text-accent-blue-700
                "
              >
                {step.label}
              </span>
              <span
                className="
                  mt-[var(--space-1)]
                  text-[length:var(--font-size-xs)] lg:text-[length:var(--font-size-sm)]
                  text-text-muted
                "
              >
                {step.sublabel}
              </span>
            </div>

            {/* Arrow between steps */}
            {index < steps.length - 1 && (
              <svg
                width="32"
                height="16"
                viewBox="0 0 32 16"
                fill="none"
                className="mx-[var(--space-1)] text-accent-blue-300 flex-shrink-0"
                aria-hidden="true"
              >
                <path
                  d="M0 8h28m0 0l-6-6m6 6l-6 6"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            )}
          </div>
        ))}
      </div>

      {/* Mobile: vertical flow */}
      <div className="flex md:hidden flex-col items-center gap-[var(--space-3)]">
        {steps.map((step, index) => (
          <div key={step.label} className="flex flex-col items-center">
            {/* Step box */}
            <div
              className="
                flex flex-col items-center justify-center
                rounded-[var(--radius-lg)]
                border border-accent-blue-200
                bg-accent-blue-50
                px-[var(--space-6)]
                py-[var(--space-3)]
                w-full max-w-[240px]
                text-center
              "
            >
              <span
                className="
                  text-[length:var(--font-size-sm)]
                  font-[var(--font-weight-semibold)]
                  text-accent-blue-700
                "
              >
                {step.label}
              </span>
              <span
                className="
                  mt-[var(--space-1)]
                  text-[length:var(--font-size-xs)]
                  text-text-muted
                "
              >
                {step.sublabel}
              </span>
            </div>

            {/* Down arrow */}
            {index < steps.length - 1 && (
              <svg
                width="16"
                height="24"
                viewBox="0 0 16 24"
                fill="none"
                className="text-accent-blue-300 flex-shrink-0"
                aria-hidden="true"
              >
                <path
                  d="M8 0v20m0 0l-6-6m6 6l6-6"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
