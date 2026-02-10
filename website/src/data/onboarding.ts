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
      "One command. No dependencies.",
  },
  {
    id: "api-key",
    number: 2,
    title: "Add Your API Key",
    description:
      "Use your existing OpenAI, Anthropic, Google, or Claude API keys. Shotgun proxies through your keys\u2014we never see your data.",
  },
  {
    id: "analyze",
    number: 3,
    title: "Analyze & Generate",
    description:
      "Point Shotgun at your repo. It analyzes your codebase, researches solutions, generates a complete spec. Review and export to your AI coding tool.",
  },
];
