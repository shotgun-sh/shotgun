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

[![Website](https://img.shields.io/badge/-shotgun.sh-5865F2?style=social&logo=safari&logoColor=5865F2)](https://shotgun.sh)      [![Follow @ShotgunCLI](https://img.shields.io/badge/Follow%20@ShotgunCLI-1DA1F2?style=social&logo=x&logoColor=000000)](https://x.com/ShotgunCLI)    [![YouTube](https://img.shields.io/badge/-@shotgunCLI-FF0000?style=social&logo=youtube&logoColor=red)](https://www.youtube.com/@shotgunCLI)

</div>

---

<table>
<tr>
<td>
  
**Shotgun is a CLI tool** that generates codebase-aware specs for AI coding agents like Cursor, Claude Code, and Lovable. **It reads your entire repository**, researches how new features should fit your architecture, and produces technical specifications that keep AI agents on track—so they build what you actually want instead of derailing halfway through. **Bring your own key (BYOK) or use a Shotgun subscription — $10 for $10 in usage.**

It includes research on existing patterns, implementation plans that respect your architecture, and task breakdowns ready to export as **AGENTS.md** files. Each spec is complete enough that your AI agent can work longer and further without losing context or creating conflicts.

<p align="center">
  <img src="https://github.com/user-attachments/assets/9c7ca014-1ed3-4935-b310-9147b275fdc7" alt="Shotgun Demo" />
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

# 🎯 Usage

Shotgun guides you through **5 phases** that turn ideas into implementation-ready specs with full codebase understanding.

### The 5-Phase Workflow

<table>
<tr>
<th width="15%">Mode</th>
<th width="40%">What It Does</th>
<th width="45%">Command</th>
</tr>

<tr>
<td><strong>1️⃣ Research</strong></td>
<td>
Searches your codebase and the web to understand what exists, find patterns, and identify constraints before you write anything.
</td>
<td>

```bash
shotgun research "add real-time collaboration"
```
</td>
</tr>

<tr>
<td><strong>2️⃣ Specify</strong></td>
<td>
Creates technical specifications based on research findings, aware of your existing architecture and patterns.
</td>
<td>

```bash
shotgun spec "Add OAuth2 authentication"
```
</td>
</tr>

<tr>
<td><strong>3️⃣ Plan</strong></td>
<td>
Generates implementation plans that respect your codebase structure, dependencies, and discovered constraints.
</td>
<td>

```bash
shotgun plan "Build user dashboard"
```
</td>
</tr>

<tr>
<td><strong>4️⃣ Tasks</strong></td>
<td>
Breaks down the plan into dependency-aware, actionable tasks with clear sequencing and priorities.
</td>
<td>

```bash
shotgun tasks "Implement payment system"
```
</td>
</tr>

<tr>
<td><strong>5️⃣ Export</strong></td>
<td>
Exports specs and tasks as <code>AGENTS.md</code> files formatted for Cursor, Claude Code, Windsurf, or Lovable.
</td>
<td>

```bash
shotgun export
```
</td>
</tr>
</table>

**Result:** Your AI coding agent now has complete context—what exists, why decisions were made, and exactly what to build.

### Quick Mode Switching

**Navigate between phases instantly using `Shift+Tab`** or by running the phase command directly.

_**💡 Visual indicator:** Shotgun's CLI shows your current phase at the bottom of the screen._

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
<td><strong>Multi-Agent Coordination</strong></td>
<td>
15+ specialized agents work in parallel (research, security, architecture) with coordinated outputs.
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

### Case Study - Real Example:

We had to implement payments. Cursor, Claude Code, and Copilot all suggested building a custom payment proxy — 3-4 weeks of development. 

⭐ Shotgun's research found [LiteLLM Proxy](https://docs.litellm.ai/docs/simple_proxy) instead—**30 minutes to discover, 5 days to deploy, first customer in 14 hours.**

****80% less dev time. Near-zero technical debt.****

### **[📖 Read the full case study](docs/CASE_STUDY.md)**

---

# Use Cases

- **🚀 Onboarding** - New developer? Shotgun maps your entire architecture and generates docs that actually match the code
- **🔧 Refactoring** - Understand all dependencies before touching anything. Keep your refactor from becoming a rewrite
- **🌱 Greenfield Projects** - Research existing solutions globally before writing line one
- **➕ Adding Features** - Know exactly where your feature fits. Prevent duplicate functionality
- **📦 Migration** - Map the old, plan the new, track the delta. Break migration into safe stages

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

## Uninstall

```bash
uv tool uninstall shotgun-sh
```

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

</div>

---

**License:** MIT | **Python:** 3.11+ | **Homepage:** [shotgun.sh](https://shotgun.sh/)
