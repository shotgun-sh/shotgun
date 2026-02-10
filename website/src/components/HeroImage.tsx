import { ResponsiveImage } from "@/components/ResponsiveImage";

export interface HeroImageProps {
  /** Image source path */
  src?: string;
  /** Alt text for accessibility */
  alt?: string;
  /** Aspect ratio for the image */
  aspectRatio?: "16:9" | "4:3";
  /** Additional CSS classes */
  className?: string;
}

/**
 * Hero visual placeholder component.
 * Displays a dashboard screenshot or workflow diagram
 * with proper aspect ratio and responsive sizing.
 *
 * When no src is provided, renders a styled placeholder
 * with a descriptive message.
 */
export function HeroImage({
  src,
  alt = "Shotgun dashboard showing intelligent spec generation workflow with codebase analysis, research, and multi-stage task export",
  aspectRatio = "16:9",
  className = "",
}: HeroImageProps) {
  if (src) {
    return (
      <div className={`w-full ${className}`}>
        <ResponsiveImage
          src={src}
          alt={alt}
          width={1280}
          height={aspectRatio === "16:9" ? 720 : 960}
          aspectRatio={aspectRatio}
          priority
          wrapperClassName="w-full shadow-[var(--shadow-xl)] border border-[var(--color-navy-600)]"
        />
      </div>
    );
  }

  // Placeholder when no image is provided
  return (
    <div
      className={`
        w-full overflow-hidden rounded-[var(--radius-lg)]
        border border-[var(--color-navy-600)]
        bg-[var(--color-navy-700)]
        shadow-[var(--shadow-xl)]
        ${aspectRatio === "16:9" ? "aspect-video" : "aspect-[4/3]"}
        ${className}
      `}
      role="img"
      aria-label={alt}
    >
      <div className="flex h-full w-full flex-col items-center justify-center gap-[var(--space-4)] p-[var(--space-8)]">
        {/* Placeholder icon: monitor/dashboard */}
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="64"
          height="64"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="text-navy-400"
          aria-hidden="true"
        >
          <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
          <line x1="8" y1="21" x2="16" y2="21" />
          <line x1="12" y1="17" x2="12" y2="21" />
          {/* Workflow arrows inside screen */}
          <path d="M6 8h2l1-2 2 4 1-2h2" />
          <line x1="14" y1="8" x2="18" y2="8" />
        </svg>
        <div className="text-center">
          <p className="text-[length:var(--font-size-sm)] font-[var(--font-weight-medium)] text-navy-300">
            Dashboard Preview
          </p>
          <p className="mt-[var(--space-1)] text-[length:var(--font-size-xs)] text-navy-400">
            Research &rarr; Spec &rarr; Plan &rarr; Tasks &rarr; Export
          </p>
        </div>
      </div>
    </div>
  );
}
