import Image, { type ImageProps } from "next/image";

export interface ResponsiveImageProps extends Omit<ImageProps, "src"> {
  /** Image source path */
  src: string;
  /** Alt text for accessibility */
  alt: string;
  /** Image width */
  width: number;
  /** Image height */
  height: number;
  /** Whether to load immediately (for hero images) */
  priority?: boolean;
  /** Optional CSS class for the wrapper */
  wrapperClassName?: string;
  /** Aspect ratio constraint */
  aspectRatio?: "16:9" | "4:3" | "1:1" | "auto";
  /** Whether to fill the container */
  fill?: boolean;
}

const aspectRatioStyles: Record<string, string> = {
  "16:9": "aspect-video",
  "4:3": "aspect-[4/3]",
  "1:1": "aspect-square",
  auto: "",
};

/**
 * ResponsiveImage component that leverages Next.js Image optimization.
 *
 * Next.js Image automatically:
 * - Generates AVIF and WebP formats
 * - Serves the best format based on browser support
 * - Creates responsive srcset with multiple sizes
 * - Lazy loads images below the fold
 * - Prevents Cumulative Layout Shift (CLS) via width/height
 *
 * For custom image formats, configure `next.config.ts` with:
 * ```ts
 * images: {
 *   formats: ['image/avif', 'image/webp'],
 * }
 * ```
 */
export function ResponsiveImage({
  src,
  alt,
  width,
  height,
  priority = false,
  wrapperClassName = "",
  aspectRatio = "auto",
  fill = false,
  className = "",
  ...props
}: ResponsiveImageProps) {
  const aspectClass = aspectRatioStyles[aspectRatio];

  if (fill) {
    return (
      <div
        className={`relative overflow-hidden rounded-[var(--radius-lg)] ${aspectClass} ${wrapperClassName}`}
      >
        <Image
          src={src}
          alt={alt}
          fill
          priority={priority}
          className={`object-cover ${className}`}
          sizes="(max-width: 768px) 100vw, (max-width: 1024px) 80vw, 1200px"
          {...props}
        />
      </div>
    );
  }

  return (
    <div
      className={`overflow-hidden rounded-[var(--radius-lg)] ${aspectClass} ${wrapperClassName}`}
    >
      <Image
        src={src}
        alt={alt}
        width={width}
        height={height}
        priority={priority}
        className={`h-auto w-full ${className}`}
        sizes="(max-width: 768px) 100vw, (max-width: 1024px) 80vw, 1200px"
        {...props}
      />
    </div>
  );
}
