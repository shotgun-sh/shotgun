import { Hero } from "@/components/Hero";

export default function Home() {
  return (
    <main className="min-h-screen">
      {/* Hero Section — above the fold, drives 70%+ of conversion */}
      <section
        className="
          min-h-[100svh] flex items-center
          bg-primary text-text-inverse
          py-[var(--space-16)] md:py-[var(--space-24)]
        "
        data-gtm-section="hero"
      >
        <div className="mx-auto w-full max-w-7xl px-[var(--space-4)] md:px-[var(--space-8)] lg:px-[var(--space-12)]">
          <Hero />
        </div>
      </section>
    </main>
  );
}
