import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Section } from "@/components/Section";
import { CodeBlock } from "@/components/CodeBlock";
import { GridLayout } from "@/components/GridLayout";
import { ResponsiveImage } from "@/components/ResponsiveImage";

/**
 * Design System Demo Page
 *
 * This page demonstrates all design tokens applied correctly:
 * - Colors (navy, orange, blue, grays)
 * - Typography (PP Supply Sans weights and sizes)
 * - Spacing scale (0.25rem – 4rem)
 * - Responsive breakpoints (320px, 768px, 1024px, 1440px)
 * - Component library (Button, Card, Section, CodeBlock, GridLayout, ResponsiveImage)
 */
export default function DemoPage() {
  return (
    <main className="min-h-screen">
      {/* ===== COLORS ===== */}
      <Section padding="lg" data-gtm-section="demo-colors">
        <h1 className="text-[length:var(--font-size-4xl)] font-[var(--font-weight-bold)] mb-[var(--space-8)]">
          Design Token Demo
        </h1>

        <h2 className="text-[length:var(--font-size-2xl)] font-[var(--font-weight-semibold)] mb-[var(--space-4)]">
          Colors
        </h2>

        <h3 className="text-[length:var(--font-size-lg)] font-[var(--font-weight-medium)] mb-[var(--space-3)] mt-[var(--space-6)]">
          Primary Navy
        </h3>
        <div className="flex flex-wrap gap-[var(--space-2)]">
          {["50", "100", "200", "300", "400", "500", "600", "700", "800", "900"].map(
            (shade) => (
              <div key={shade} className="text-center">
                <div
                  className="h-16 w-16 rounded-[var(--radius-md)] border border-border"
                  style={{ backgroundColor: `var(--color-navy-${shade})` }}
                />
                <span className="text-[length:var(--font-size-xs)] text-text-muted mt-1 block">
                  {shade}
                </span>
              </div>
            ),
          )}
        </div>

        <h3 className="text-[length:var(--font-size-lg)] font-[var(--font-weight-medium)] mb-[var(--space-3)] mt-[var(--space-6)]">
          Accent Orange
        </h3>
        <div className="flex flex-wrap gap-[var(--space-2)]">
          {["50", "100", "200", "300", "400", "500", "600", "700"].map(
            (shade) => (
              <div key={shade} className="text-center">
                <div
                  className="h-16 w-16 rounded-[var(--radius-md)] border border-border"
                  style={{ backgroundColor: `var(--color-orange-${shade})` }}
                />
                <span className="text-[length:var(--font-size-xs)] text-text-muted mt-1 block">
                  {shade}
                </span>
              </div>
            ),
          )}
        </div>

        <h3 className="text-[length:var(--font-size-lg)] font-[var(--font-weight-medium)] mb-[var(--space-3)] mt-[var(--space-6)]">
          Accent Blue
        </h3>
        <div className="flex flex-wrap gap-[var(--space-2)]">
          {["50", "100", "200", "300", "400", "500", "600", "700"].map(
            (shade) => (
              <div key={shade} className="text-center">
                <div
                  className="h-16 w-16 rounded-[var(--radius-md)] border border-border"
                  style={{ backgroundColor: `var(--color-blue-${shade})` }}
                />
                <span className="text-[length:var(--font-size-xs)] text-text-muted mt-1 block">
                  {shade}
                </span>
              </div>
            ),
          )}
        </div>

        <h3 className="text-[length:var(--font-size-lg)] font-[var(--font-weight-medium)] mb-[var(--space-3)] mt-[var(--space-6)]">
          Grays
        </h3>
        <div className="flex flex-wrap gap-[var(--space-2)]">
          {["50", "100", "200", "300", "400", "500", "600", "700", "800", "900", "950"].map(
            (shade) => (
              <div key={shade} className="text-center">
                <div
                  className="h-16 w-16 rounded-[var(--radius-md)] border border-border"
                  style={{ backgroundColor: `var(--color-gray-${shade})` }}
                />
                <span className="text-[length:var(--font-size-xs)] text-text-muted mt-1 block">
                  {shade}
                </span>
              </div>
            ),
          )}
        </div>

        <h3 className="text-[length:var(--font-size-lg)] font-[var(--font-weight-medium)] mb-[var(--space-3)] mt-[var(--space-6)]">
          Semantic Colors
        </h3>
        <div className="flex flex-wrap gap-[var(--space-4)]">
          <div className="text-center">
            <div className="h-16 w-16 rounded-[var(--radius-md)] bg-primary" />
            <span className="text-[length:var(--font-size-xs)] text-text-muted block">Primary</span>
          </div>
          <div className="text-center">
            <div className="h-16 w-16 rounded-[var(--radius-md)] bg-accent" />
            <span className="text-[length:var(--font-size-xs)] text-text-muted block">Accent</span>
          </div>
          <div className="text-center">
            <div className="h-16 w-16 rounded-[var(--radius-md)] bg-secondary" />
            <span className="text-[length:var(--font-size-xs)] text-text-muted block">Secondary</span>
          </div>
          <div className="text-center">
            <div className="h-16 w-16 rounded-[var(--radius-md)] bg-success" />
            <span className="text-[length:var(--font-size-xs)] text-text-muted block">Success</span>
          </div>
          <div className="text-center">
            <div className="h-16 w-16 rounded-[var(--radius-md)] bg-error" />
            <span className="text-[length:var(--font-size-xs)] text-text-muted block">Error</span>
          </div>
        </div>
      </Section>

      {/* ===== TYPOGRAPHY ===== */}
      <Section background="surface" padding="lg" data-gtm-section="demo-typography">
        <h2 className="text-[length:var(--font-size-2xl)] font-[var(--font-weight-semibold)] mb-[var(--space-6)]">
          Typography
        </h2>

        <div className="space-y-[var(--space-4)]">
          <div>
            <span className="text-[length:var(--font-size-xs)] text-text-muted block mb-1">
              6xl / 60px / Bold
            </span>
            <p className="text-[length:var(--font-size-6xl)] font-[var(--font-weight-bold)] leading-[var(--line-height-tight)]">
              Intelligent Specs
            </p>
          </div>
          <div>
            <span className="text-[length:var(--font-size-xs)] text-text-muted block mb-1">
              5xl / 48px / Bold
            </span>
            <p className="text-[length:var(--font-size-5xl)] font-[var(--font-weight-bold)] leading-[var(--line-height-tight)]">
              Not Templates
            </p>
          </div>
          <div>
            <span className="text-[length:var(--font-size-xs)] text-text-muted block mb-1">
              4xl / 36px / Semibold
            </span>
            <p className="text-[length:var(--font-size-4xl)] font-[var(--font-weight-semibold)]">
              Your Codebase Understanding
            </p>
          </div>
          <div>
            <span className="text-[length:var(--font-size-xs)] text-text-muted block mb-1">
              3xl / 30px / Semibold
            </span>
            <p className="text-[length:var(--font-size-3xl)] font-[var(--font-weight-semibold)]">
              Research Before Building
            </p>
          </div>
          <div>
            <span className="text-[length:var(--font-size-xs)] text-text-muted block mb-1">
              2xl / 24px / Medium
            </span>
            <p className="text-[length:var(--font-size-2xl)] font-[var(--font-weight-medium)]">
              Ship Faster. Stop Reinventing Wheels.
            </p>
          </div>
          <div>
            <span className="text-[length:var(--font-size-xs)] text-text-muted block mb-1">
              xl / 20px / Regular
            </span>
            <p className="text-[length:var(--font-size-xl)] font-[var(--font-weight-regular)]">
              Shotgun analyzes your codebase, researches existing solutions, and generates contextual specs.
            </p>
          </div>
          <div>
            <span className="text-[length:var(--font-size-xs)] text-text-muted block mb-1">
              base / 16px / Regular
            </span>
            <p className="text-[length:var(--font-size-base)] font-[var(--font-weight-regular)]">
              No credit card. $10 = $10 usage. Works with Cursor, Claude Code, Windsurf, and more.
            </p>
          </div>
          <div>
            <span className="text-[length:var(--font-size-xs)] text-text-muted block mb-1">
              sm / 14px / Regular
            </span>
            <p className="text-[length:var(--font-size-sm)] text-text-secondary">
              Install in seconds. No dependencies. No setup.
            </p>
          </div>
          <div>
            <span className="text-[length:var(--font-size-xs)] text-text-muted block mb-1">
              xs / 12px / Regular
            </span>
            <p className="text-[length:var(--font-size-xs)] text-text-muted">
              Monospace: font-family: var(--font-family-mono)
            </p>
          </div>
        </div>
      </Section>

      {/* ===== SPACING ===== */}
      <Section padding="lg" data-gtm-section="demo-spacing">
        <h2 className="text-[length:var(--font-size-2xl)] font-[var(--font-weight-semibold)] mb-[var(--space-6)]">
          Spacing Scale
        </h2>
        <div className="space-y-[var(--space-3)]">
          {[
            { name: "space-1", value: "0.25rem / 4px" },
            { name: "space-2", value: "0.5rem / 8px" },
            { name: "space-3", value: "0.75rem / 12px" },
            { name: "space-4", value: "1rem / 16px" },
            { name: "space-5", value: "1.25rem / 20px" },
            { name: "space-6", value: "1.5rem / 24px" },
            { name: "space-8", value: "2rem / 32px" },
            { name: "space-10", value: "2.5rem / 40px" },
            { name: "space-12", value: "3rem / 48px" },
            { name: "space-16", value: "4rem / 64px" },
          ].map(({ name, value }) => (
            <div key={name} className="flex items-center gap-[var(--space-4)]">
              <div
                className="h-6 rounded-[var(--radius-sm)] bg-secondary"
                style={{ width: `var(--${name})` }}
              />
              <span className="text-[length:var(--font-size-sm)] text-text-secondary min-w-32">
                --{name}
              </span>
              <span className="text-[length:var(--font-size-xs)] text-text-muted">
                {value}
              </span>
            </div>
          ))}
        </div>
      </Section>

      {/* ===== BUTTONS ===== */}
      <Section background="surface" padding="lg" data-gtm-section="demo-buttons">
        <h2 className="text-[length:var(--font-size-2xl)] font-[var(--font-weight-semibold)] mb-[var(--space-6)]">
          Button Component
        </h2>

        <h3 className="text-[length:var(--font-size-lg)] font-[var(--font-weight-medium)] mb-[var(--space-3)]">
          Variants
        </h3>
        <div className="flex flex-wrap gap-[var(--space-3)] mb-[var(--space-6)]">
          <Button variant="primary" data-gtm-event="demo_btn_primary">Primary</Button>
          <Button variant="secondary" data-gtm-event="demo_btn_secondary">Secondary</Button>
          <Button variant="accent" data-gtm-event="demo_btn_accent">Accent</Button>
          <Button variant="ghost" data-gtm-event="demo_btn_ghost">Ghost</Button>
        </div>

        <h3 className="text-[length:var(--font-size-lg)] font-[var(--font-weight-medium)] mb-[var(--space-3)]">
          Sizes
        </h3>
        <div className="flex flex-wrap items-center gap-[var(--space-3)] mb-[var(--space-6)]">
          <Button variant="primary" size="sm">Small</Button>
          <Button variant="primary" size="md">Medium</Button>
          <Button variant="primary" size="lg">Large</Button>
        </div>

        <h3 className="text-[length:var(--font-size-lg)] font-[var(--font-weight-medium)] mb-[var(--space-3)]">
          States
        </h3>
        <div className="flex flex-wrap items-center gap-[var(--space-3)]">
          <Button variant="primary">Default</Button>
          <Button variant="primary" disabled>Disabled</Button>
          <Button variant="primary" loading>Loading</Button>
        </div>
      </Section>

      {/* ===== CARDS ===== */}
      <Section padding="lg" data-gtm-section="demo-cards">
        <h2 className="text-[length:var(--font-size-2xl)] font-[var(--font-weight-semibold)] mb-[var(--space-6)]">
          Card Component
        </h2>

        <GridLayout columns={2} gap="md">
          <Card variant="default" title="Default Card">
            <p className="text-[length:var(--font-size-sm)] text-text-secondary">
              Default card with border and background.
            </p>
          </Card>
          <Card variant="elevated" title="Elevated Card">
            <p className="text-[length:var(--font-size-sm)] text-text-secondary">
              Elevated card with shadow.
            </p>
          </Card>
          <Card variant="outlined" title="Outlined Card">
            <p className="text-[length:var(--font-size-sm)] text-text-secondary">
              Outlined card with transparent background.
            </p>
          </Card>
          <Card variant="filled" hoverable title="Hoverable Card">
            <p className="text-[length:var(--font-size-sm)] text-text-secondary">
              Filled card with hover effect. Try hovering!
            </p>
          </Card>
        </GridLayout>
      </Section>

      {/* ===== CODE BLOCKS ===== */}
      <Section background="surface" padding="lg" data-gtm-section="demo-code">
        <h2 className="text-[length:var(--font-size-2xl)] font-[var(--font-weight-semibold)] mb-[var(--space-6)]">
          CodeBlock Component
        </h2>

        <div className="space-y-[var(--space-6)]">
          <div>
            <h3 className="text-[length:var(--font-size-lg)] font-[var(--font-weight-medium)] mb-[var(--space-3)]">
              Bash (with prompt)
            </h3>
            <CodeBlock
              code="uvx shotgun-sh@latest"
              language="bash"
              data-gtm-event="demo_code_bash"
            />
          </div>

          <div>
            <h3 className="text-[length:var(--font-size-lg)] font-[var(--font-weight-medium)] mb-[var(--space-3)]">
              JavaScript (with line numbers)
            </h3>
            <CodeBlock
              code={`import { Shotgun } from 'shotgun-sh';

const spec = await Shotgun.analyze({
  repo: './my-project',
  provider: 'anthropic',
});

console.log(spec.stages);`}
              language="javascript"
              showLineNumbers
              showPrompt={false}
              filename="example.js"
            />
          </div>

          <div>
            <h3 className="text-[length:var(--font-size-lg)] font-[var(--font-weight-medium)] mb-[var(--space-3)]">
              Python
            </h3>
            <CodeBlock
              code={`from shotgun import analyze

result = analyze(
    repo="./my-project",
    provider="openai",
)

for stage in result.stages:
    print(f"Stage: {stage.name}")`}
              language="python"
              showPrompt={false}
              filename="example.py"
            />
          </div>

          <div>
            <h3 className="text-[length:var(--font-size-lg)] font-[var(--font-weight-medium)] mb-[var(--space-3)]">
              JSON
            </h3>
            <CodeBlock
              code={`{
  "name": "shotgun-sh",
  "version": "1.0.0",
  "stages": 5,
  "research": true,
  "providers": ["openai", "anthropic", "google"]
}`}
              language="json"
              showPrompt={false}
              showLineNumbers
            />
          </div>
        </div>
      </Section>

      {/* ===== RESPONSIVE IMAGE ===== */}
      <Section padding="lg" data-gtm-section="demo-images">
        <h2 className="text-[length:var(--font-size-2xl)] font-[var(--font-weight-semibold)] mb-[var(--space-6)]">
          ResponsiveImage Component
        </h2>

        <div className="space-y-[var(--space-6)]">
          <div>
            <h3 className="text-[length:var(--font-size-lg)] font-[var(--font-weight-medium)] mb-[var(--space-3)]">
              Hero Image (16:9)
            </h3>
            <ResponsiveImage
              src="/images/placeholder-hero.svg"
              alt="Shotgun dashboard showing codebase analysis, spec generation, and multi-stage workflow"
              width={1200}
              height={800}
              priority
              aspectRatio="16:9"
            />
          </div>
        </div>
      </Section>

      {/* ===== RESPONSIVE GRID TEST ===== */}
      <Section background="surface" padding="lg" data-gtm-section="demo-responsive">
        <h2 className="text-[length:var(--font-size-2xl)] font-[var(--font-weight-semibold)] mb-[var(--space-4)]">
          Responsive Grid Test
        </h2>
        <p className="text-[length:var(--font-size-sm)] text-text-secondary mb-[var(--space-6)]">
          Resize your browser to see layout changes at each breakpoint:
          <br />
          <strong>320px</strong> (mobile) → <strong>768px</strong> (tablet) → <strong>1024px</strong> (desktop) → <strong>1440px</strong> (wide)
        </p>

        {/* Current breakpoint indicator */}
        <div className="mb-[var(--space-6)] rounded-[var(--radius-lg)] bg-navy-800 p-[var(--space-4)] text-text-inverse text-center">
          <span className="block md:hidden lg:hidden xl:hidden text-[length:var(--font-size-lg)] font-[var(--font-weight-bold)]">
            📱 Mobile (&lt;768px)
          </span>
          <span className="hidden md:block lg:hidden xl:hidden text-[length:var(--font-size-lg)] font-[var(--font-weight-bold)]">
            📱 Tablet (768px–1023px)
          </span>
          <span className="hidden md:hidden lg:block xl:hidden text-[length:var(--font-size-lg)] font-[var(--font-weight-bold)]">
            💻 Desktop (1024px–1439px)
          </span>
          <span className="hidden md:hidden lg:hidden xl:block text-[length:var(--font-size-lg)] font-[var(--font-weight-bold)]">
            🖥️ Wide Desktop (1440px+)
          </span>
        </div>

        {/* 2-column grid */}
        <h3 className="text-[length:var(--font-size-lg)] font-[var(--font-weight-medium)] mb-[var(--space-3)]">
          2-Column Grid
        </h3>
        <GridLayout columns={2} gap="md" className="mb-[var(--space-8)]">
          {[1, 2, 3, 4].map((n) => (
            <Card key={n} variant="outlined">
              <p className="text-[length:var(--font-size-base)] font-[var(--font-weight-medium)] text-center">
                Card {n}
              </p>
            </Card>
          ))}
        </GridLayout>

        {/* 3-column grid */}
        <h3 className="text-[length:var(--font-size-lg)] font-[var(--font-weight-medium)] mb-[var(--space-3)]">
          3-Column Grid
        </h3>
        <GridLayout columns={3} gap="md" className="mb-[var(--space-8)]">
          {[1, 2, 3, 4, 5, 6].map((n) => (
            <Card key={n} variant="outlined">
              <p className="text-[length:var(--font-size-base)] font-[var(--font-weight-medium)] text-center">
                Card {n}
              </p>
            </Card>
          ))}
        </GridLayout>

        {/* 4-column grid */}
        <h3 className="text-[length:var(--font-size-lg)] font-[var(--font-weight-medium)] mb-[var(--space-3)]">
          4-Column Grid
        </h3>
        <GridLayout columns={4} gap="md">
          {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => (
            <Card key={n} variant="outlined">
              <p className="text-[length:var(--font-size-base)] font-[var(--font-weight-medium)] text-center">
                {n}
              </p>
            </Card>
          ))}
        </GridLayout>
      </Section>

      {/* ===== SECTION VARIANTS ===== */}
      <Section background="primary" padding="md" data-gtm-section="demo-section-primary">
        <h2 className="text-[length:var(--font-size-2xl)] font-[var(--font-weight-semibold)]">
          Section: Primary Background
        </h2>
        <p className="text-[length:var(--font-size-base)] text-navy-200 mt-[var(--space-2)]">
          This section uses the primary navy background with inverse text.
        </p>
      </Section>

      <Section background="accent" padding="md" data-gtm-section="demo-section-accent">
        <h2 className="text-[length:var(--font-size-2xl)] font-[var(--font-weight-semibold)]">
          Section: Accent Background
        </h2>
        <p className="text-[length:var(--font-size-base)] text-text-secondary mt-[var(--space-2)]">
          This section uses the accent orange-50 background.
        </p>
      </Section>

      {/* ===== GTM TRACKING TEST ===== */}
      <Section padding="lg" data-gtm-section="demo-tracking">
        <h2 className="text-[length:var(--font-size-2xl)] font-[var(--font-weight-semibold)] mb-[var(--space-6)]">
          Analytics Tracking Test
        </h2>
        <p className="text-[length:var(--font-size-sm)] text-text-secondary mb-[var(--space-4)]">
          Open your browser console and click these elements. You should see
          GTM event payloads logged with the correct structure.
        </p>
        <div className="flex flex-wrap gap-[var(--space-3)]">
          <Button
            variant="accent"
            size="lg"
            data-gtm-event="hero_cta_signup"
          >
            Start Free with BYOK
          </Button>
          <Button
            variant="primary"
            data-gtm-event="demo_cta_learn_more"
          >
            Learn More
          </Button>
        </div>
        <div className="mt-[var(--space-4)]">
          <CodeBlock
            code="uvx shotgun-sh@latest"
            language="bash"
            data-gtm-event="demo_code_copy"
          />
        </div>
      </Section>
    </main>
  );
}
