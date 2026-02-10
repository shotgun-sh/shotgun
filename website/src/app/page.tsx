import { Hero } from "@/components/Hero";
import { ProblemSection } from "@/components/ProblemSection";
import { SolutionSection } from "@/components/SolutionSection";
import { WorkflowDiagram } from "@/components/WorkflowDiagram";
import { FeaturesSection } from "@/components/FeaturesSection";
import { ComparisonSection } from "@/components/ComparisonSection";
import { SocialProofSection } from "@/components/SocialProofSection";
import { GettingStartedSection } from "@/components/GettingStartedSection";
import { FinalCTASection } from "@/components/FinalCTASection";
import { ScrollTracker } from "@/components/ScrollTracker";

export default function Home() {
  return (
    <main id="main-content" className="min-h-screen">
      {/* Hero Section — above the fold, drives 70%+ of conversion */}
      <section
        className="
          min-h-[100svh] flex items-center
          bg-primary text-text-inverse
          py-[var(--space-16)] md:py-[var(--space-24)]
        "
        data-gtm-section="hero"
        aria-labelledby="hero-heading"
      >
        <div className="mx-auto w-full max-w-7xl px-[var(--space-4)] md:px-[var(--space-8)] lg:px-[var(--space-12)]">
          <Hero heroImageSrc="/images/hero-dashboard.svg" />
        </div>
      </section>

      {/* Problem Section — validates developer pain points */}
      <section
        className="
          bg-[var(--color-background)]
          py-[var(--space-16)] md:py-[var(--space-24)]
        "
        data-gtm-section="problems"
        aria-labelledby="problems-heading"
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
        aria-labelledby="solutions-heading"
      >
        <ScrollTracker sectionName="solutions">
          <div className="mx-auto w-full max-w-7xl px-[var(--space-4)] md:px-[var(--space-8)] lg:px-[var(--space-12)]">
            <SolutionSection />

            {/* Workflow Diagram — visual reinforcement below solution cards */}
            <WorkflowDiagram className="mt-[var(--space-16)]" />
          </div>
        </ScrollTracker>
      </section>

      {/* Features Section — concrete benefits list */}
      <section
        className="
          bg-[var(--color-background)]
          py-[var(--space-16)] md:py-[var(--space-24)]
        "
        data-gtm-section="features"
        aria-labelledby="features-heading"
      >
        <ScrollTracker sectionName="features">
          <div className="mx-auto w-full max-w-7xl px-[var(--space-4)] md:px-[var(--space-8)] lg:px-[var(--space-12)]">
            <FeaturesSection />
          </div>
        </ScrollTracker>
      </section>

      {/* Social Proof Section — LiteLLM case study + competitive scoring */}
      <section
        id="social-proof"
        className="
          bg-surface
          py-[var(--space-16)] md:py-[var(--space-24)]
        "
        data-gtm-section="social-proof"
        aria-labelledby="social-proof-heading"
      >
        <ScrollTracker sectionName="social-proof">
          <div className="mx-auto w-full max-w-7xl px-[var(--space-4)] md:px-[var(--space-8)] lg:px-[var(--space-12)]">
            <SocialProofSection />
          </div>
        </ScrollTracker>
      </section>

      {/* Comparison Section — Intelligence vs Templates positioning */}
      <section
        id="comparison"
        className="
          bg-[var(--color-background)]
          py-[var(--space-16)] md:py-[var(--space-24)]
        "
        data-gtm-section="comparison"
        aria-labelledby="comparison-heading"
      >
        <ScrollTracker sectionName="comparison">
          <div className="mx-auto w-full max-w-7xl px-[var(--space-4)] md:px-[var(--space-8)] lg:px-[var(--space-12)]">
            <ComparisonSection />
          </div>
        </ScrollTracker>
      </section>

      {/* Getting Started Section — 3-step onboarding guide */}
      <section
        className="
          bg-surface
          py-[var(--space-16)] md:py-[var(--space-24)]
        "
        data-gtm-section="getting-started"
        aria-labelledby="getting-started-heading"
      >
        <ScrollTracker sectionName="getting-started">
          <div className="mx-auto w-full max-w-7xl px-[var(--space-4)] md:px-[var(--space-8)] lg:px-[var(--space-12)]">
            <GettingStartedSection />
          </div>
        </ScrollTracker>
      </section>

      {/* Final CTA Section — compelling close with primary CTA */}
      <section
        className="
          bg-primary text-text-inverse
          py-[var(--space-16)] md:py-[var(--space-24)]
        "
        data-gtm-section="final-cta"
        aria-labelledby="final-cta-heading"
      >
        <ScrollTracker sectionName="final-cta">
          <div className="mx-auto w-full max-w-7xl px-[var(--space-4)] md:px-[var(--space-8)] lg:px-[var(--space-12)]">
            <FinalCTASection />
          </div>
        </ScrollTracker>
      </section>
    </main>
  );
}
