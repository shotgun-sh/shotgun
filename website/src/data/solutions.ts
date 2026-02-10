export interface SolutionData {
  /** Unique identifier */
  id: string;
  /** Solution title */
  title: string;
  /** Bold benefit statement */
  benefit: string;
  /** Detailed description copy */
  copy: string;
}

/**
 * Four solution cards mirroring the problem cards.
 * Copy sourced from specification.md Section 4.
 */
export const solutions: SolutionData[] = [
  {
    id: "persistent-understanding",
    title: "Codebase Context That Persists",
    benefit: "Your specs know what already exists. No rebuilding. No architectural conflicts.",
    copy: "Shotgun indexes your entire repository using tree-sitter parsing. It understands your dependencies, patterns, existing code. This understanding persists across sessions. Your AI agent never forgets what you\u2019ve built.",
  },
  {
    id: "research-first",
    title: "Research Before Building",
    benefit: "Discover existing solutions. Save weeks of custom development.",
    copy: "Shotgun researches existing libraries, frameworks, and tools before specifying. It answers \u2018should we build this or use something that exists?\u2019 before your AI agent starts coding.",
  },
  {
    id: "multi-stage",
    title: "Multi-Stage Execution Plans",
    benefit: "Complex features broken into execution stages. Each stage is one AI session\u2019s worth of work.",
    copy: "Instead of handing your AI agent a 50-page spec, Shotgun breaks complex features into 3\u20135 execution stages. Each stage is sized for a single session. Review between stages. Stay aligned.",
  },
  {
    id: "agent-orchestration",
    title: "Specialized Agents for Each Phase",
    benefit: "Research phase, spec phase, planning phase, execution phase\u2014each with the right expertise.",
    copy: "A research agent explores and discovers. A spec agent captures requirements. A planning agent creates roadmaps. A task agent breaks into executable steps. Each brings expertise to its phase.",
  },
];
