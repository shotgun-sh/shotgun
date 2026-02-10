export interface FeatureData {
  /** Unique identifier */
  id: string;
  /** Feature title */
  title: string;
  /** One-line benefit statement */
  benefit: string;
}

/**
 * Eight feature highlights for the "What You Get" section.
 * Copy sourced from specification.md Section 5.
 */
export const features: FeatureData[] = [
  {
    id: "codebase-analysis",
    title: "Codebase Analysis",
    benefit: "Understand your architecture before proposing changes.",
  },
  {
    id: "web-search",
    title: "Built-in Web Search",
    benefit: "Research existing solutions in minutes, not hours.",
  },
  {
    id: "multi-agent",
    title: "Multi-Agent Orchestration",
    benefit: "Specialized expertise for research, spec, planning, and execution.",
  },
  {
    id: "pr-staging",
    title: "PR-Ready Task Staging",
    benefit: "Each task is one AI session\u2019s work. Git integration for tracking.",
  },
  {
    id: "multi-tool",
    title: "Multi-Tool Export",
    benefit: "Works with Cursor, Claude Code, Windsurf, Codex, Lovable. Not locked in.",
  },
  {
    id: "llm-flexibility",
    title: "LLM Provider Flexibility",
    benefit: "OpenAI, Anthropic, Google, or bring your own API key.",
  },
  {
    id: "persistent-workspace",
    title: "Persistent Workspace",
    benefit: "Specs persist across sessions. Team members can review, comment, iterate.",
  },
  {
    id: "one-command",
    title: "One-Command Install",
    benefit: "Instant setup. No dependencies. Works locally or in your CI/CD.",
  },
];
