import type { HTMLAttributes, ReactNode } from "react";

export interface SectionProps extends HTMLAttributes<HTMLElement> {
  /** Section content */
  children: ReactNode;
  /** Background color variant */
  background?: "default" | "primary" | "surface" | "accent";
  /** Vertical padding size */
  padding?: "sm" | "md" | "lg" | "xl";
  /** Whether to constrain content width */
  contained?: boolean;
  /** GTM section tracking attribute */
  "data-gtm-section"?: string;
}

const backgroundStyles: Record<string, string> = {
  default: "bg-[var(--color-background)]",
  primary: "bg-primary text-text-inverse",
  surface: "bg-surface",
  accent: "bg-accent-orange-50",
};

const paddingStyles: Record<string, string> = {
  sm: "py-[var(--space-8)]",
  md: "py-[var(--space-12)]",
  lg: "py-[var(--space-16)]",
  xl: "py-[var(--space-24)]",
};

export function Section({
  children,
  background = "default",
  padding = "md",
  contained = true,
  className = "",
  "data-gtm-section": gtmSection,
  ...props
}: SectionProps) {
  return (
    <section
      className={`
        ${backgroundStyles[background]}
        ${paddingStyles[padding]}
        ${className}
      `}
      data-gtm-section={gtmSection}
      {...props}
    >
      {contained ? (
        <div className="mx-auto max-w-7xl px-[var(--space-4)] md:px-[var(--space-8)] lg:px-[var(--space-12)]">
          {children}
        </div>
      ) : (
        children
      )}
    </section>
  );
}
