export interface ComparisonRow {
  /** Unique identifier for tracking */
  id: string;
  /** Decision factor / aspect being compared */
  aspect: string;
  /** Shotgun's capability (the advantage) */
  shotgun: string;
  /** Spec Kit's capability */
  specKit: string;
  /** Whether Shotgun has a clear advantage (used for visual emphasis) */
  shotgunAdvantage: boolean;
}

/**
 * Comparison data for "Intelligence vs Templates" section.
 * Data sourced from specification.md Section 7.
 */
export const comparisonRows: ComparisonRow[] = [
  {
    id: "codebase-analysis",
    aspect: "Codebase Analysis",
    shotgun: "Reads entire repo, understands patterns and dependencies",
    specKit: "No indexing; depends on what you tell it",
    shotgunAdvantage: true,
  },
  {
    id: "research",
    aspect: "Research",
    shotgun: "Built-in web search discovers solutions before building",
    specKit: "No research; you research externally",
    shotgunAdvantage: true,
  },
  {
    id: "spec-generation",
    aspect: "Spec Generation",
    shotgun: "Automatically generated from codebase analysis",
    specKit: "Manual\u2014you write the spec yourself",
    shotgunAdvantage: true,
  },
  {
    id: "workflow",
    aspect: "Workflow Enforcement",
    shotgun: "5-stage enforced workflow with checkpoints",
    specKit: "Optional templates; you decide the process",
    shotgunAdvantage: true,
  },
  {
    id: "context-persistence",
    aspect: "Context Persistence",
    shotgun: "Graph database remembers decisions across sessions",
    specKit: "No persistent context; depends on your memory",
    shotgunAdvantage: true,
  },
  {
    id: "agent-sophistication",
    aspect: "Agent Sophistication",
    shotgun: "Specialized agents for research, spec, planning, execution",
    specKit: "No agents; templates only",
    shotgunAdvantage: true,
  },
  {
    id: "export",
    aspect: "Export Targets",
    shotgun: "Optimized for 5+ AI tools (Cursor, Claude Code, Windsurf, etc.)",
    specKit: "Portable Markdown (works anywhere, optimized nowhere)",
    shotgunAdvantage: true,
  },
  {
    id: "collaboration",
    aspect: "Team Collaboration",
    shotgun: "Built-in workspace with versioning and review",
    specKit: "Git-based; no dedicated collab features",
    shotgunAdvantage: true,
  },
  {
    id: "setup",
    aspect: "Setup Complexity",
    shotgun: "One command: uvx shotgun-sh@latest",
    specKit: "Clone repo, use templates",
    shotgunAdvantage: true,
  },
  {
    id: "cost",
    aspect: "Cost",
    shotgun: "Free with BYOK, $10 = $10 usage",
    specKit: "Free (open source)",
    shotgunAdvantage: false,
  },
];
