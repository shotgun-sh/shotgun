/**
 * Getting Started onboarding steps data.
 *
 * 3-step guide from specification.md:
 * 1. Install Shotgun
 * 2. Add Your API Key
 * 3. Analyze & Generate
 */

export interface OnboardingStepData {
  id: string;
  number: number;
  title: string;
  description: string;
}

export const onboardingSteps: OnboardingStepData[] = [
  {
    id: "install",
    number: 1,
    title: "Install Shotgun",
    description:
      "One command. No dependencies. Works on macOS, Linux, and WSL. You're ready in seconds.",
  },
  {
    id: "api-key",
    number: 2,
    title: "Add Your API Key",
    description:
      "Use your existing OpenAI, Anthropic, Google, or Claude API keys. BYOK means your money, your usage.",
  },
  {
    id: "analyze",
    number: 3,
    title: "Analyze & Generate",
    description:
      "Point Shotgun at your repo. It analyzes your codebase, researches solutions, and generates a complete spec.",
  },
];
