import type { HTMLAttributes, ReactNode } from "react";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** Card content */
  children: ReactNode;
  /** Visual style variant */
  variant?: "default" | "elevated" | "outlined" | "filled";
  /** Whether to show a hover effect */
  hoverable?: boolean;
  /** Optional icon to display in the card header */
  icon?: ReactNode;
  /** Optional card title */
  title?: string;
  /** Optional padding override */
  padding?: "sm" | "md" | "lg";
}

const variantStyles: Record<string, string> = {
  default:
    "bg-surface-elevated border border-border",
  elevated:
    "bg-surface-elevated shadow-[var(--shadow-md)]",
  outlined:
    "bg-transparent border border-border",
  filled:
    "bg-surface",
};

const paddingStyles: Record<string, string> = {
  sm: "p-[var(--space-3)]",
  md: "p-[var(--space-5)]",
  lg: "p-[var(--space-8)]",
};

export function Card({
  children,
  variant = "default",
  hoverable = false,
  icon,
  title,
  padding = "md",
  className = "",
  ...props
}: CardProps) {
  return (
    <div
      className={`
        rounded-[var(--radius-lg)]
        transition-all duration-[var(--transition-base)]
        ${variantStyles[variant]}
        ${paddingStyles[padding]}
        ${hoverable ? "hover:shadow-[var(--shadow-lg)] hover:-translate-y-0.5" : ""}
        ${className}
      `}
      {...props}
    >
      {(icon || title) && (
        <div className="mb-[var(--space-3)] flex items-center gap-[var(--space-3)]">
          {icon && (
            <div className="flex h-10 w-10 items-center justify-center rounded-[var(--radius-md)] bg-navy-50 text-navy-600">
              {icon}
            </div>
          )}
          {title && (
            <h3 className="text-[length:var(--font-size-lg)] font-[var(--font-weight-semibold)] text-text-primary">
              {title}
            </h3>
          )}
        </div>
      )}
      {children}
    </div>
  );
}
