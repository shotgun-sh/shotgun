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

<details>
<summary><strong>Windows Installation</strong></summary>

```powershell
# Set execution policy (one-time)
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force

# Install uv
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Add to PATH (or restart terminal)
$env:Path = "C:\Users\$env:USERNAME\.local\bin;$env:Path"

# Run Shotgun (ephemeral)
uvx --python 3.12 shotgun-sh@latest

# Or install permanently
uv tool install --python 3.12 shotgun-sh
```

| Supported | Not Supported |
|-----------|---------------|
| Windows x64 (regular PCs) | 32-bit Python |
| Python 3.11-3.13 | Python 3.14+ (no wheels yet) |

**Important:** Run in **PowerShell**, not Command Prompt or VS Developer shells.

#### Optional: Enable Code Indexing

Code indexing requires the Visual C++ Redistributable. Run this in PowerShell (as Administrator):

```powershell
# Download and install Visual C++ Redistributable
Import-Module BitsTransfer
Start-BitsTransfer -Source "https://aka.ms/vs/17/release/vc_redist.x64.exe" -Destination "$env:TEMP\vc_redist.x64.exe"
Start-Process -FilePath "$env:TEMP\vc_redist.x64.exe" -ArgumentList "/install", "/quiet", "/norestart" -Wait
```

</details>

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

> [!WARNING]
> **Upgrading from alpha?** Uninstall the old version first:
> ```bash
> npm uninstall -g @proofs-io/shotgun @proofs-io/shotgun-server
> ```

---

# 🎥 Demo

<p align="center">
  <a href="https://youtu.be/nR6iKbJ8l_I">
    <img src="https://github.com/user-attachments/assets/37eae206-0d6f-4499-b980-2f33a5aed65d" alt="Watch the Shotgun demo" width="720" height="405">
  </a>
</p>

_Click the image above to watch the full demo on YouTube_

---

# 🎯 Usage

### Launch Shotgun in your project directory:

| Already Installed | First Time / Try It Out |
|-------------------|------------------------|
| `shotgun` | `uvx shotgun-sh@latest` |

Shotgun's Terminal UI runs a Router that orchestrates your work using two execution modes: **Planning** and **Drafting**.

### Planning vs Drafting

| Mode | How It Works | When to Use It |
|------|--------------|---------------|
| **Planning** (default) | Shotgun proposes an execution plan, shows each step, and asks for confirmation before running agents that change files. You get checkpoints, can refine the plan, and can confirm or skip cascaded updates when one change affects other docs. | When you want control, visibility, and the ability to refine the plan before execution. |
| **Drafting** | Shotgun runs the full plan in one go, without intermediate confirmations. Progress is still tracked internally, but you won’t be prompted at each step. | When you’re confident in the plan and want fast, end-to-end execution. |

_The TUI opens automatically. **Press `Shift+Tab` to switch between Planning & Drafting** or `Ctrl+P` for the command palette._

### How the Router Works Internally
Under the hood, the Router relies on specialized sub-agents. You don’t select or manage them manually.

<table>
<tr>
<td align="center"><b>🔬 Research</b><br/>Explore & understand</td>
<td align="center">→</td>
<td align="center"><b>📝 Specify</b><br/>Define requirements</td>
<td align="center">→</td>
<td align="center"><b>📋 Plan</b><br/>Create roadmap</td>
<td align="center">→</td>
<td align="center"><b>✅ Tasks</b><br/>Break into steps</td>
<td align="center">→</td>
<td align="center"><b>📤 Export</b><br/>Format for AI</td>
</tr>
</table>

> Planning and Drafting are the only execution modes you control; everything else is handled by the Router.

_**Mode switching:** `Shift+Tab` cycles through modes_

### ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Shift+Tab` | Switch modes |
| `Ctrl+P` | Open command palette |
| `Ctrl+C` | Cancel operation |
| `Escape` | Exit Q&A / stop agent |
| `Ctrl+U` | View usage stats |

### Tips for Better Results

| Do This | Not This |
|---------|----------|
| ✅ `Research how we handle auth` | ❌ Jump straight to building |
| ✅ `Shotgun please ask me questions first` | ❌ Assume Shotgun knows your needs |
| ✅ `I'm working on payments, need refunds` | ❌ `Add refunds` (no context) |
| ✅ Start in Planning mode, let Shotgun propose and refine a plan with you, then run it | ❌ Blast everything in one go without reviewing the plan first (unless you intentionally switch to Drafting mode) |

**Result:** Your AI coding agent gets complete context—what exists, why, and what to build.

 **Note:** CLI available in [docs/CLI.md](docs/CLI.md), but TUI is recommended.

---

# 🤝 Share Specs with Your Team

Sharing specs to a workspace is available on **paid Shotgun plans**.

Shotgun lets you share specs externally by publishing them to a **workspace**. This creates a versioned, shareable snapshot your team can access outside the repo.

### How to Share a Spec

1. Hit `Ctrl+P` → select _Share specs to workspace_
2. Choose one option:
- **Create new spec** — publish a fresh spec from your current `.shotgun/` files
- **Add new version** — publish an updated version of an existing spec
3. Wait for upload to complete. When finished, you can:
- **Open in Browser** — view the shared spec in the workspace
- **Copy URL** — share the link with your team
- **Done** — return to Shotgun
<img width="516" height="181" alt="image" src="https://github.com/user-attachments/assets/6dd9412c-345e-4dab-a40a-ad5f1c994d34" />


Your local `.shotgun/*.md` files remain unchanged.  
The workspace contains a **shareable, versioned snapshot** of the spec.

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
Router-driven flow with Planning and Drafting modes; internally it runs Research → Spec → Plan → Tasks → Export with checkpoints in Planning mode.
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

**📚 Want to see a detailed example?** Check out our [Case Study](docs/CASE_STUDY.md) showing Shotgun in action on a real-world project.

---

# FAQ

**Q: Does Shotgun collect any stats or data?**

A: We only gather minimal, anonymous events (e.g., install, server start, tool call). We don't collect the content itself—only that an event occurred. We use Sentry for error reporting to improve stability.

**Q: Does my code leave my computer when indexing?**

A: No. When you index your codebase, all indexing happens locally on your machine. The index is stored in `~/.shotgun-sh/codebases/` and never sent to any server. Your code stays on your computer.

![Indexing Privacy](docs/index_codebase_privacy.png)

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

**Planning → Drafting** — Two execution modes that give AI agents the full picture, backed by internal phases for Research → Specify → Plan → Tasks → Export.

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
