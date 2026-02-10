import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Section } from "@/components/Section";
import { CodeBlock } from "@/components/CodeBlock";
import { GridLayout } from "@/components/GridLayout";
import { ResponsiveImage } from "@/components/ResponsiveImage";

export default function Home() {
  return (
    <main className="min-h-screen">
      {/* Hero Section Placeholder */}
      <Section background="primary" padding="lg">
        <h1 className="text-[length:var(--font-size-5xl)] font-[var(--font-weight-bold)] leading-[var(--line-height-tight)] text-text-inverse">
          Intelligent Specs, Not Templates.
        </h1>
        <p className="mt-[var(--space-4)] text-[length:var(--font-size-xl)] text-navy-200">
          Where Spec Kit gives you a blank template, Shotgun analyzes your
          codebase, researches existing solutions, and generates contextual
          specs.
        </p>
        <div className="mt-[var(--space-8)] flex flex-col gap-[var(--space-4)] md:flex-row md:items-center">
          <Button variant="accent" size="lg" data-gtm-event="hero_cta_signup">
            Start Free with BYOK
          </Button>
          <CodeBlock
            code="uvx shotgun-sh@latest"
            language="bash"
            showLineNumbers={false}
            data-gtm-event="hero_code_copy"
          />
        </div>
        <p className="mt-[var(--space-4)] text-[length:var(--font-size-sm)] text-navy-300">
          No credit card. $10 = $10 usage. Works with Cursor, Claude Code,
          Windsurf, and more.
        </p>
      </Section>

      {/* Demo Grid Section */}
      <Section padding="lg">
        <h2 className="text-[length:var(--font-size-3xl)] font-[var(--font-weight-bold)]">
          Component Demo
        </h2>
        <GridLayout columns={2} gap="md" className="mt-[var(--space-8)]">
          <Card>
            <h3 className="text-[length:var(--font-size-xl)] font-[var(--font-weight-semibold)]">
              Button Variants
            </h3>
            <div className="mt-[var(--space-4)] flex flex-wrap gap-[var(--space-3)]">
              <Button variant="primary" size="md">
                Primary
              </Button>
              <Button variant="secondary" size="md">
                Secondary
              </Button>
              <Button variant="accent" size="md">
                Accent
              </Button>
              <Button variant="ghost" size="md">
                Ghost
              </Button>
            </div>
          </Card>
          <Card>
            <h3 className="text-[length:var(--font-size-xl)] font-[var(--font-weight-semibold)]">
              Code Block
            </h3>
            <div className="mt-[var(--space-4)]">
              <CodeBlock code="uvx shotgun-sh@latest" language="bash" />
            </div>
          </Card>
          <Card>
            <h3 className="text-[length:var(--font-size-xl)] font-[var(--font-weight-semibold)]">
              Responsive Image
            </h3>
            <div className="mt-[var(--space-4)]">
              <ResponsiveImage
                src="/images/placeholder-hero.svg"
                alt="Placeholder hero image"
                width={600}
                height={400}
                priority
              />
            </div>
          </Card>
          <Card>
            <h3 className="text-[length:var(--font-size-xl)] font-[var(--font-weight-semibold)]">
              Design Tokens
            </h3>
            <div className="mt-[var(--space-4)] space-y-[var(--space-2)]">
              <div className="flex items-center gap-[var(--space-3)]">
                <div className="h-8 w-8 rounded-[var(--radius-sm)] bg-primary" />
                <span className="text-[length:var(--font-size-sm)]">
                  Primary Navy
                </span>
              </div>
              <div className="flex items-center gap-[var(--space-3)]">
                <div className="h-8 w-8 rounded-[var(--radius-sm)] bg-accent" />
                <span className="text-[length:var(--font-size-sm)]">
                  Accent Orange
                </span>
              </div>
              <div className="flex items-center gap-[var(--space-3)]">
                <div className="h-8 w-8 rounded-[var(--radius-sm)] bg-secondary" />
                <span className="text-[length:var(--font-size-sm)]">
                  Secondary Blue
                </span>
              </div>
              <div className="flex items-center gap-[var(--space-3)]">
                <div className="h-8 w-8 rounded-[var(--radius-sm)] bg-text-muted" />
                <span className="text-[length:var(--font-size-sm)]">
                  Gray/Muted
                </span>
              </div>
            </div>
          </Card>
        </GridLayout>
      </Section>
    </main>
  );
}
