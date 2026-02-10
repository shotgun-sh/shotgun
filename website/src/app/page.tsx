import { Hero } from "@/components/Hero";
import { ProblemSection } from "@/components/ProblemSection";
import { SolutionSection } from "@/components/SolutionSection";
import { WorkflowDiagram } from "@/components/WorkflowDiagram";
import { ScrollTracker } from "@/components/ScrollTracker";

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

      {/* Problem Section — validates developer pain points */}
      <section
        className="
          bg-[var(--color-background)]
          py-[var(--space-16)] md:py-[var(--space-24)]
        "
        data-gtm-section="problems"
      >
        <ScrollTracker sectionName="problems">
          <div className="mx-auto w-full max-w-7xl px-[var(--space-4)] md:px-[var(--space-8)] lg:px-[var(--space-12)]">
            <ProblemSection />
          </div>
        </ScrollTracker>
      </section>

      {/* Solution Section — introduces core features in parallel */}
      <section
        className="
          bg-surface
          py-[var(--space-16)] md:py-[var(--space-24)]
        "
        data-gtm-section="solutions"
      >
        <ScrollTracker sectionName="solutions">
          <div className="mx-auto w-full max-w-7xl px-[var(--space-4)] md:px-[var(--space-8)] lg:px-[var(--space-12)]">
            <SolutionSection />

            {/* Workflow Diagram — visual reinforcement below solution cards */}
            <WorkflowDiagram className="mt-[var(--space-16)]" />
          </div>
        </ScrollTracker>
      </section>
    </main>
  );
}
