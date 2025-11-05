<div align="center">
<img width="400" height="150" alt="Shotgun logo transparent background" src="https://github.com/user-attachments/assets/08f9ccd5-f2e8-4bf4-9cb2-2f0de866a76a" />  

### Spec-Driven Development

**Write codebase-aware specs for AI coding agents (Codex, Cursor, Claude Code) so they don't derail.**
<p align="center">
  <a href="https://github.com/shotgun-sh/shotgun">
    <img src="https://img.shields.io/badge/python-3.11+-blue?style=flat&logo=python&logoColor=white" />
  </a>
  <a href="https://www.producthunt.com/products/shotgun-cli/launches/shotgun-cli">
    <img src="https://img.shields.io/badge/Product%20Hunt-%237%20Product%20of%20the%20Day-FF6154?style=flat&logo=producthunt&logoColor=white" />
  </a>
  <a href="https://github.com/shotgun-sh/shotgun?tab=contributing-ov-file">
    <img src="https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat" />
  </a>
  <a href="https://github.com/shotgun-sh/shotgun?tab=MIT-1-ov-file">
    <img src="https://img.shields.io/badge/license-MIT-blue?style=flat" />
  </a>
  <a href="https://discord.com/invite/5RmY6J2N7s">
    <img src="https://img.shields.io/badge/discord-150+%20online-5865F2?style=flat&logo=discord&logoColor=white" />
  </a>
</p>

[Website](https://shotgun.sh) • [X.com](https://x.com/ShotgunCLI) • [YouTube](https://www.youtube.com/@shotgunCLI)
</div>

---

<table>
<tr>
<td>
  
**Shotgun is a CLI tool** that generates codebase-aware specs for AI coding agents like Cursor, Claude Code, and Lovable. **It reads your entire repository**, researches how new features should fit your architecture, and produces technical specifications that keep AI agents on track—so they build what you actually want instead of derailing halfway through.

It includes research on existing patterns, implementation plans that respect your architecture, and task breakdowns ready to export as **AGENTS.md** files. Each spec is complete enough that your AI agent can work longer and further without losing context or creating conflicts.

<p align="center">
  <a href="https://www.youtube.com/watch?v=3e7kxhANXWA">
    <img src="https://img.youtube.com/vi/3e7kxhANXWA/maxresdefault.jpg" alt="Watch the Shotgun demo" width="720" height="450">
  </a>
</p>

</td>
</tr>
</table>

---

# 📦 Installation

### 1. Install uv

Shotgun runs via `uvx` or `uv tool install`. First, install `uv` for your platform:

<table>
<tr>
<th>Platform</th>
<th>Installation Command</th>
</tr>
<tr>
<td><strong>macOS</strong> (Homebrew)</td>
<td>

```bash
brew install uv
```
</td>
</tr>
<tr>
<td><strong>macOS/Linux</strong> (curl)</td>
<td>

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
</td>
</tr>
<tr>
<td><strong>Windows</strong> (PowerShell)</td>
<td>

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"       
```
</td>
</tr>
</table>

_💡 Restart your terminal after installation_

### 2. Run Shotgun

<table>
<tr>
<th>🚀 Try It Out (Ephemeral)</th>
<th>⚡ Regular Use (Permanent)</th>
</tr>
<tr>
<td>
  
**Best for:** Testing Shotgun first

```bash
uvx shotgun-sh@latest    
```

No installation needed, runs immediately

</td>
<td>

**Best for:** Daily use

```bash
uv tool install shotgun-sh       
```

Then run anywhere: ``` shotgun ```

</td>
</tr>
</table>

_**Why uv?** It's 10-100x faster than pip and handles binary wheels reliably—no cmake/build tool errors._

### 3. Get Started

When you launch Shotgun, it will guide you through:

| Step | What Happens |
|------|--------------|
| **1. Codebase Indexing** | Builds a searchable graph of your entire repository |
| **2. LLM Setup** | Configure OpenAI, Anthropic, or Gemini |
| **3. First Research** | Start generating codebase-aware specs |

_**💡 Pro tip:** Run Shotgun in your IDE's terminal for the best experience._

---

> [!WARNING]
> **Upgrading from alpha?** Uninstall the old version first:
> ```bash
> npm uninstall -g @proofs-io/shotgun @proofs-io/shotgun-server
> ```

---

# 🎥 Demo

Watch this quick demo to see Shotgun in action:

<p align="center">
  <a href="https://www.youtube.com/watch?v=3e7kxhANXWA">
    <img src="https://img.youtube.com/vi/3e7kxhANXWA/maxresdefault.jpg" alt="Watch the Shotgun demo" width="720" height="405">
  </a>
</p>

_Click the image above to watch the full demo on YouTube_

---

# 🎯 Usage

Shotgun guides you through **5 specialized modes**, each designed for a specific phase of the development workflow. Each mode uses a dedicated AI agent with prompts tailored for that phase, and writes to its own file in `.shotgun/`.

## The 5 Modes Explained

### 🔬 1. Research Mode

**Purpose:** Research topics with web search and synthesize findings. Perfect for gathering information and exploring new concepts before writing any specs.

**What it does:**
- Searches your codebase to understand existing patterns and architecture
- Performs web research to find best practices and external solutions
- Synthesizes findings into actionable insights
- Identifies constraints and opportunities

**Writes to:** `.shotgun/research.md`

**When to use:** Start here when exploring new features, investigating problems, or onboarding to understand the codebase.

**Example prompts:**
- "How do we handle authentication in this codebase?"
- "Research best practices for implementing real-time collaboration"
- "What patterns do we use for database access?"

---

### 📝 2. Specify Mode

**Purpose:** Create detailed specifications and requirements documents. Great for planning features and documenting requirements based on your research.

**What it does:**
- Creates technical specifications aware of your existing architecture
- Documents functional and non-functional requirements
- Defines acceptance criteria and success metrics
- References discovered patterns from research

**Writes to:** `.shotgun/specification.md`

**When to use:** After research, when you need a clear specification before implementation planning.

**Example prompts:**
- "Add OAuth2 authentication with refresh token support"
- "User profile management system with avatar uploads"
- "Specify a notification system with email and SMS"

---

### 📋 3. Plan Mode

**Purpose:** Create actionable implementation plans with milestones. Ideal for breaking down large projects into manageable steps.

**What it does:**
- Generates implementation plans respecting your codebase structure
- Breaks work into logical phases with clear milestones
- Identifies dependencies and sequencing requirements
- Considers risks and mitigation strategies

**Writes to:** `.shotgun/plan.md`

**When to use:** After specification, when you need a structured approach to implementation.

**Example prompts:**
- "Build user dashboard with analytics widgets"
- "Migrate authentication system to OAuth2"
- "Create an implementation plan for the payment system"

---

### ✅ 4. Tasks Mode

**Purpose:** Generate specific, actionable tasks from research and plans. Best for getting concrete next steps and action items.

**What it does:**
- Breaks down plans into dependency-aware actionable tasks
- Provides clear sequencing and priorities
- Includes implementation details and file references
- Tracks what needs to be done and in what order

**Writes to:** `.shotgun/tasks.md`

**When to use:** After planning, when you're ready to start implementation and need clear action items.

**Example prompts:**
- "Create the tasks for implementing the OAuth2 system"
- "Break down the user dashboard plan into tasks"
- "What are the specific steps to implement this feature?"

---

### 📤 5. Export Mode

**Purpose:** Export artifacts and findings to various formats. Creates documentation like `AGENTS.md` (AI agent instructions), `PRD.md` (Product Requirements), and other deliverables.

**What it does:**
- Exports research, specs, plans, and tasks to AI agent formats
- Generates `AGENTS.md` files for Cursor, Claude Code, Windsurf, Lovable
- Creates PRDs, technical documentation, and other artifacts
- Formats content for your chosen AI coding tool

**Writes to:** `.shotgun/AGENTS.md`, `.shotgun/PRD.md`, and other custom files in `.shotgun/`

**When to use:** When you're ready to hand off to your AI coding agent or need to generate documentation.

**Example prompts:**
- "Export everything to AGENTS.md"
- "Create a PRD for the authentication feature"
- "Generate documentation for the new payment system"

---

## Using the Interactive TUI

Launch Shotgun to start the interactive Terminal User Interface:

<table>
<tr>
<th>If Installed</th>
<th>If Not Installed (Try First)</th>
</tr>
<tr>
<td>

```bash
shotgun
```

After running `uv tool install shotgun-sh`

</td>
<td>

```bash
uvx shotgun-sh@latest
```

No installation needed, runs immediately

</td>
</tr>
</table>

**TUI Features:**
- 🔄 **Switch modes:** Press `Shift+Tab` to cycle through modes, or `Ctrl+P` to open command palette
- 💬 **Natural conversation:** Chat naturally with the AI - it understands context and your current mode
- 📊 **Visual indicators:** Current mode, status, and progress shown at bottom of screen
- ⚡ **Keyboard shortcuts:**
  - `Ctrl+P` - Open command palette
  - `Shift+Tab` - Switch between modes
  - `Ctrl+C` - Cancel current operation
  - `Escape` - Exit Q&A mode or cancel current agent processing
  - `Ctrl+U` - View usage statistics

**Getting Started:**
1. Launch Shotgun in your project directory (see table above)
2. Start with Research mode to explore your codebase
3. Progress through the modes as needed
4. Export your specifications when ready

> **Note:** CLI commands are available but the TUI is the recommended way to use Shotgun. See [docs/CLI.md](docs/CLI.md) for CLI usage.

## Tips for Better Results

### 1. Ask for Research First
Before jumping into a task, let Shotgun research the codebase:

> "Can you research how authentication works in this codebase?"

### 2. Request Clarifying Questions
Let Shotgun ask you questions to better understand your needs:

> "I want to add user profiles. Please ask me clarifying questions before starting."

### 3. Use the Right Mode
- Use **Research** for exploration and understanding
- Use **Specify** for requirements and specifications
- Use **Plan** for implementation strategy
- Use **Tasks** for actionable next steps
- Use **Export** to generate AI agent instructions

### 4. Provide Context
Give relevant context about what you're trying to accomplish:

> "I'm working on the payment flow. I need to add support for refunds."

**Result:** Your AI coding agent now has complete context—what exists, why decisions were made, and exactly what to build.

---

# ✨ Features

### What Makes Shotgun Different

<table>
<tr>
<th width="25%">Feature</th>
<th width="35%">Shotgun</th>
<th width="40%">Other Tools</th>
</tr>

<tr>
<td><strong>Codebase Understanding</strong></td>
<td>
Reads your <strong>entire repository</strong> before generating specs. Finds existing patterns, dependencies, and architecture.
</td>
<td>
Require manual context or search each time. No persistent understanding of your codebase structure.
</td>
</tr>

<tr>
<td><strong>Research Phase</strong></td>
<td>
Starts with research—discovers what you already have AND what exists externally before writing anything.
</td>
<td>
Start at specification. Build first, discover problems later.
</td>
</tr>

<tr>
<td><strong>Dedicated Agents Per Mode</strong></td>
<td>
Each mode (research, spec, plan, tasks, export) uses a <strong>separate specialized agent</strong> with prompts tailored specifically for that phase. 100% user-controllable via mode switching.
</td>
<td>
Single-agent or one-size-fits-all prompts.
</td>
</tr>

<tr>
<td><strong>Structured Workflow</strong></td>
<td>
5-phase journey with checkpoints: Research → Spec → Plan → Tasks → Export
</td>
<td>
No structure. Just "prompt and hope."
</td>
</tr>

<tr>
<td><strong>Export Formats</strong></td>
<td>
<code>AGENTS.md</code> files ready for Cursor, Claude Code, Windsurf, Lovable—your choice of tool.
</td>
<td>
Locked into specific IDE or coding agent.
</td>
</tr>

</table>

### Why It Matters

**The Problem:** AI coding agents are fast at generating code but have no idea what you already built or why past decisions were made.

**The Solution:** Shotgun gives AI agents the full picture—your codebase context, architectural patterns, and research findings—so they build what you actually need instead of creating conflicts.

---

# Use Cases

- **🚀 Onboarding** - New developer? Shotgun maps your entire architecture and generates docs that actually match the code
- **🔧 Refactoring** - Understand all dependencies before touching anything. Keep your refactor from becoming a rewrite
- **🌱 Greenfield Projects** - Research existing solutions globally before writing line one
- **➕ Adding Features** - Know exactly where your feature fits. Prevent duplicate functionality
- **📦 Migration** - Map the old, plan the new, track the delta. Break migration into safe stages

**📚 Want to see a detailed example?** Check out our [Case Study](docs/CASE_STUDY.md) showing Shotgun in action on a real-world project.

---

# FAQ

**Q: Does Shotgun collect any stats or data?**

A: We only gather minimal, anonymous events (e.g., install, server start, tool call). We don't collect the content itself—only that an event occurred. We use Sentry for error reporting to improve stability.

**Q: Local LLMs?**

A: Planned. We'll publish compatibility notes and local provider integrations.

**Q: What LLM providers are supported?**

A: Currently OpenAI, Anthropic (Claude), and Google Gemini. Local LLM support is on the roadmap.

**Q: Can I use Shotgun offline?**

A: You need an internet connection for LLM API calls, but your codebase stays local.

**Q: How does the code graph work?**

A: Shotgun indexes your codebase using tree-sitter for accurate parsing and creates a searchable graph of your code structure, dependencies, and relationships.

---
# Contributing

Shotgun is open-source and we welcome contributions. Whether you're fixing bugs, proposing features, improving docs, or spreading the word—we'd love to have you as part of the community.

### Ways to contribute:

- **Bug Report:** Found an issue? [Create a bug report](https://github.com/shotgun-sh/shotgun/issues/new?template=bug_report.md)
- **Feature Request:** Have an idea to make Shotgun better? [Submit a feature request](https://github.com/shotgun-sh/shotgun/issues/new?template=feature_request.md)
- **Documentation:** See something missing in the docs? [Request documentation](https://github.com/shotgun-sh/shotgun/issues/new?template=documentation.md)

**Not sure where to start?** Join our Discord and we'll help you get started!

<div align="left">
  <a href="https://discord.com/invite/5RmY6J2N7s">
    <img src="https://img.shields.io/badge/Join%20our%20community-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Join Discord" />
  </a>
</div>

### Development Resources

- **[Contributing Guide](docs/CONTRIBUTING.md)** - Setup, workflow, and guidelines
- **[Git Hooks](docs/GIT_HOOKS.md)** - Lefthook, trufflehog, and security scanning
- **[CI/CD](docs/CI_CD.md)** - GitHub Actions and automated testing
- **[Observability](docs/OBSERVABILITY.md)** - Telemetry, Logfire, and monitoring
- **[Docker](docs/DOCKER.md)** - Container setup and deployment

---

<div align="center">

## 🚀 Ready to Stop AI Agents from Derailing?

**Research → Specify → Plan → Tasks → Export** — Five phases that give AI agents the full picture.

```bash
uvx shotgun-sh@latest
```


### ⭐ Star us on GitHub


<a href="https://github.com/shotgun-sh/shotgun">
  <img src="https://img.shields.io/badge/⭐%20Star%20on%20GitHub-181717?style=for-the-badge&logo=github&logoColor=white" alt="Star Shotgun Repo" />
</a>

### Star History

<a href="https://www.star-history.com/#shotgun-sh/shotgun&type=date&legend=bottom-right">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=shotgun-sh/shotgun&type=date&theme=dark&legend=bottom-right" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=shotgun-sh/shotgun&type=date&legend=bottom-right" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=shotgun-sh/shotgun&type=date&legend=bottom-right" />
 </picture>
</a>

</div>

---

**License:** MIT | **Python:** 3.11+ | **Homepage:** [shotgun.sh](https://shotgun.sh/)

---

## Uninstall

```bash
uv tool uninstall shotgun-sh
```
