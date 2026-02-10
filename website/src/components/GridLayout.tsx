import type { HTMLAttributes, ReactNode } from "react";

export interface GridLayoutProps extends HTMLAttributes<HTMLDivElement> {
  /** Grid content (children) */
  children: ReactNode;
  /** Number of columns on desktop */
  columns?: 1 | 2 | 3 | 4;
  /** Gap size between grid items */
  gap?: "sm" | "md" | "lg";
  /** Whether items should have equal heights */
  equalHeight?: boolean;
}

const columnStyles: Record<number, string> = {
  1: "grid-cols-1",
  2: "grid-cols-1 md:grid-cols-2",
  3: "grid-cols-1 md:grid-cols-2 lg:grid-cols-3",
  4: "grid-cols-1 md:grid-cols-2 lg:grid-cols-4",
};

const gapStyles: Record<string, string> = {
  sm: "gap-[var(--space-3)]",
  md: "gap-[var(--space-6)]",
  lg: "gap-[var(--space-8)]",
};

export function GridLayout({
  children,
  columns = 2,
  gap = "md",
  equalHeight = true,
  className = "",
  ...props
}: GridLayoutProps) {
  return (
    <div
      className={`
        grid
        ${columnStyles[columns]}
        ${gapStyles[gap]}
        ${equalHeight ? "auto-rows-fr" : ""}
        ${className}
      `}
      {...props}
    >
      {children}
    </div>
  );
}
