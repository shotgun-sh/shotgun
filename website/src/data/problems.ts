export interface ProblemData {
  /** Unique identifier */
  id: string;
  /** Problem title */
  title: string;
  /** Problem description copy */
  copy: string;
}

/**
 * Four core developer pain points for the Problem section.
 * Copy sourced from specification.md Section 3.
 */
export const problems: ProblemData[] = [
  {
    id: "context-loss",
    title: "Context Loss Between Sessions",
    copy: "Across multiple sessions on a complex feature, your AI agent loses sight of earlier decisions. It proposes conflicting architectures. It rebuilds what you already built.",
  },
  {
    id: "scope-creep",
    title: "Scope Creep & Derailing",
    copy: "Plan mode gives your AI agent general direction, not a detailed spec. It adds what seems helpful. You ship features you didn\u2019t ask for.",
  },
  {
    id: "rebuilding",
    title: "Rebuilding Existing Functionality",
    copy: "Your AI agent doesn\u2019t understand your existing codebase patterns. It suggests building a custom auth system when you already have one. It rebuilds instead of integrating.",
  },
  {
    id: "no-research",
    title: "No Research Before Building",
    copy: "Should you build custom or use an existing solution? Your AI agent guesses. It suggests building because that\u2019s easier to spec than researching alternatives.",
  },
];
