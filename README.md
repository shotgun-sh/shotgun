<p align="center">
  <a href="https://discord.com/invite/5RmY6J2N7s">
    <img src="https://img.shields.io/badge/Discord-Join%20Us-5865F2?logo=discord&logoColor=white" />
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/License-MIT-green.svg" />
  </a>
</p>

<div align="center">

# SHOTGUN — Beta

<img width="600" height="200" alt="Shotgun Logo" src="docs/shotgun_logo.png" />

### Shotgun is a CLI that turns what you want to work on into _research → specs → plans → tasks → implementation_ with full codebase understanding and agents doing the heavy lifting.

It produces clean, reusable artifacts and exports to the [agents.md](https://github.com/openai/agents.md) ecosystem to help you get the most out of code-gen tools and Agents.

```bash
uvx shotgun-sh@latest
```

</div>

---

## Table of Contents

- [Quickstart](#quickstart)
- [Why Shotgun?](#why-shotgun)
- [How It Works](#how-it-works)
- [Core Features](#core-features)
- [Use Cases](#use-cases)
- [Demo](#demo)
- [Installation](#installation)
- [Usage](#usage)
- [Auto-Updates](#auto-updates)
- [Docker](#docker)
- [Roadmap](#roadmap)
- [FAQ](#faq)
- [Contributing](#contributing)
- [Support](#support)

---

<h2 id="quickstart">Quickstart</h2>

Shotgun is installed via `uvx` or `uv tool install`. First, install uv for your platform:

> [!WARNING]
> If you tried out an alpha version of shotgun, make sure to uninstall it:
> `npm uninstall -g @proofs-io/shotgun @proofs-io/shotgun-server`

### Step 1: Install uv

#### macOS

**Using Homebrew (recommended):**
```bash
brew install uv
```

**Using curl:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### Linux

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### Windows

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

_Restart your terminal after installation_

---

### Step 2: Run Shotgun

Once uv is installed, run shotgun using one of these methods:

**Option 1: Ephemeral execution (recommended for trying out)**
```bash
uvx shotgun-sh@latest
```

**Option 2: Permanent installation (recommended for regular use)**
```bash
uv tool install shotgun-sh
```

Then run:
```bash
shotgun
```

**Why uv?** It's 10-100x faster than other package managers and handles binary wheels reliably, preventing build errors on systems without cmake/build tools.

---

### Step 3: Get Started

**Shotgun will guide you through:**

- Indexing your codebase into a searchable graph
- Setting up your LLM provider (OpenAI, Anthropic, or Gemini)
- Starting your first research session

**Pro tip:** Run Shotgun in your IDE's terminal for the best experience.

---

## What You Get Today

- **Spec-driven workflow** across five Modes: `research → specify → plan → tasks → implement`
- **Deterministic artifacts** you can version in Git
- **Export to agents.md** so outputs plug into many code-generation tools (Codex, Cursor, Warp, Devin, opencode, Jules and so on)
- **Local-first CLI** with minimal setup

> Shotgun sits _under_ your codegen tools: it creates the structured inputs those tools need and keeps them consistent across the lifecycle.

---

## Why Shotgun?

### 🎯 **Know your code. Decide faster.**

- Answers grounded in your actual repo via a live code graph—no guessing or stale context
- Cut research time: query your codebase, web, GitHub, and docs in one place
- Turn clarity into action with specs and plans that stay in sync with your project

### 🚀 **From idea to shipped—without chaos.**

- Five guided modes: Research → Spec → Plan → Tasks → Export
- Structured, editable artifacts live in your repo for review and clean handoffs
- Export specs/tasks to any AI tool or workflow and keep a single source of truth

### 🛡️ **AI speed with production-grade safety.**

- Codebase-aware guardrails, conflict detection, and architecture constraints keep work on track
- Human-in-the-loop checkpoints and streamed progress give control when it matters
- Telemetry and change tracking reduce rework and late-night incidents

---

## How It Works

1. **Install & Connect** - Point at your repo. Shotgun builds a live code graph.
2. **Research What Exists** - Ask in plain English: "How do we handle auth?" Shotgun queries your code graph AND searches npm, GitHub, docs.
3. **Choose Your Mode** - Research → Specify → Plan → Tasks → Export. Start anywhere. Each mode has specialized agents.
4. **Review & Guide** - Watch agents work in your terminal. See what they find. Approve key decisions.
5. **Export to Any Tool** - Export artifacts into agents.md format to drive downstream tools

---

## Core Features

### 📊 **Complete Codebase Understanding**

Before writing a single line, Shotgun reads all of it. Your patterns. Your dependencies. Your technical debt. Whether you're adding features, onboarding devs, planning migrations, or refactoring - Shotgun knows what you're working with.

### 🔄 **Five Modes. One Journey. Zero Gaps.**

**Research** (what exists) → **Specify** (what to build) → **Plan** (how to build) → **Tasks** (break it down) → **Export** (to any tool)

Not another chatbot. A complete workflow where each mode feeds the next.

### 📝 **Specs That Don't Die in Slack**

Every research finding, every architectural decision, every "here's why we didn't use that library" - captured as markdown in your repo. Version controlled. Searchable.

### ➡️ **Export to agents.md**

Outputs plug into many code-generation tools including Codex, Cursor, Warp, Devin, opencode, Jules, and more.

---

## Use Cases

- **🚀 Onboarding** - New developer? Shotgun maps your entire architecture and generates docs that actually match the code
- **🔧 Refactoring** - Understand all dependencies before touching anything. Keep your refactor from becoming a rewrite
- **🌱 Greenfield Projects** - Research existing solutions globally before writing line one
- **➕ Adding Features** - Know exactly where your feature fits. Prevent duplicate functionality
- **📦 Migration** - Map the old, plan the new, track the delta. Break migration into safe stages

---

<h2 id="demo">Demo</h2>

**See Shotgun in action:**

<p align="center">
  <a href="https://www.youtube.com/watch?v=3e7kxhANXWA">
    <img src="https://img.youtube.com/vi/3e7kxhANXWA/maxresdefault.jpg" alt="Watch the Shotgun demo" width="720" height="450">
  </a>
</p>

**Give Shotgun a spin:**

```bash
Onboard me to this codebase.
```

---

## Installation

### Using uvx (Recommended)

**Quick start (ephemeral):**
```bash
uvx shotgun-sh@latest
```

**Install permanently:**
```bash
uv tool install shotgun-sh
```

If you don't have `uv` installed, get it at [astral.sh/uv](https://astral.sh/uv) or:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### From Source

```bash
git clone https://github.com/shotgun-sh/shotgun.git
cd shotgun
uv sync --all-extras
```

After installation from source, you can use either method:

**Method 1: Direct command (after uv sync)**
```bash
shotgun --help
```

**Method 2: Via uv run**
```bash
uv run shotgun --help
```

### Virtual Environment Setup (Optional)

If you prefer using a local virtual environment:

```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv sync --all-extras
shotgun --help
```

---

## Usage

### Using Direct Commands (after uv sync)

```bash
# Research a topic
shotgun research "What is quantum computing?"

# Generate a specification
shotgun spec "Add OAuth2 authentication"

# Create a plan
shotgun plan "Build a web application"

# Generate tasks for a project
shotgun tasks "Create a machine learning model"

# Export to agents.md
shotgun export
```

### Using uv run

```bash
# Research a topic
uv run shotgun research "What is quantum computing?"

# Generate a plan
uv run shotgun plan "Build a web application"

# Generate tasks for a project
uv run shotgun tasks "Create a machine learning model"
```

---

## Auto-Updates

Shotgun automatically checks for updates to keep you on the latest version.

### How it works

- Checks for updates on startup (runs in background, non-blocking)
- Caches results for 24 hours to minimize API calls
- Shows notification after command execution if an update is available
- Never auto-updates development versions

### Update Commands

```bash
# Check for available updates
shotgun update --check

# Install available updates
shotgun update

# Force update (even for dev versions with confirmation)
shotgun update --force
```

### Disable Update Checks

```bash
# Disable for a single command
shotgun --no-update-check research "topic"
```

### Installation Methods

The update command automatically detects and uses the appropriate method:
- **uvx**: Run `uvx shotgun-sh@latest` again or use `uv tool install shotgun-sh` for permanent installation
- **uv tool**: `uv tool upgrade shotgun-sh`
- **venv**: Updates within the virtual environment

---

## Docker

Run Shotgun in a Docker container with web access. Perfect for deployment and isolated environments.

### Quick Start

```bash
cd /path/to/your/project

docker run -p 8000:8000 \
  -v $(pwd):/workspace \
  -v ~/.shotgun-sh:/home/shotgun/.shotgun-sh \
  ghcr.io/shotgun-sh/shotgun:latest
```

Access the web interface at **http://localhost:8000**

### Available Images

- **`latest`** - ✅ **Recommended** - Latest stable release
- **`v0.1.0`** - Specific version tags
- **`dev`** - ❌ **Not recommended** - Development version (for developers only)

For detailed Docker documentation including custom ports, background mode, troubleshooting, and more, see [Docker Guide](docs/DOCKER.md).

---

<h2 id="roadmap">Roadmap</h2>

### 🚧 Coming Soon

- [ ] Token usage display & spend tracking
- [ ] Support for local LLMs
- [ ] Linear agents integration
- [ ] Attachments: add screenshots / PDFs / files to Shotgun
- [ ] Performance improvements (make Shotgun faster)

---

## FAQ

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

<h2 id="contributing">Contributing</h2>

Shotgun is in Beta — we'd love your feedback and support!

We welcome contributions! Whether you're fixing bugs, adding features, or improving documentation, your help makes Shotgun better.

### Get Started

- Join our [Discord community](https://discord.gg/5RmY6J2N7s)
- Read the [Contributing Guide](docs/CONTRIBUTING.md)
- Check out [open issues](https://github.com/shotgun-sh/shotgun/issues)
- Review the [Git Hooks documentation](docs/GIT_HOOKS.md)

### Development Resources

- **[Contributing Guide](docs/CONTRIBUTING.md)** - Setup, workflow, and guidelines
- **[Git Hooks](docs/GIT_HOOKS.md)** - Lefthook, trufflehog, and security scanning
- **[CI/CD](docs/CI_CD.md)** - GitHub Actions and automated testing
- **[Observability](docs/OBSERVABILITY.md)** - Telemetry, Logfire, and monitoring
- **[Docker](docs/DOCKER.md)** - Container setup and deployment

---

## Support

**Join our community:**
- [Discord](https://discord.gg/5RmY6J2N7s) - Get help and discuss Shotgun
- [GitHub Issues](https://github.com/shotgun-sh/shotgun/issues) - Report bugs and request features
- [Website](https://shotgun.sh) - Learn more about Shotgun
- [Product Hunt](https://www.producthunt.com/posts/shotgun) - We hit #7 on Product Hunt!

### Uninstall

```bash
uv tool uninstall shotgun-sh
```

### Troubleshooting

**Do you have the old version of Shotgun? (shotgun-alpha)**

Uninstall the shotgun alpha (previous version):

```bash
npm uninstall -g @proofs-io/shotgun --loglevel=error
npm uninstall -g @proofs-io/shotgun-server --loglevel=error
```

---

<div align="center">

<h2>🚀 Ready to write specs that truly capture your intents?</h2>

<p><strong>Research (what exists) → Specify (what to build) → Plan (how to build) → Tasks (break it down) → Export (to any tool)</strong></p>

<pre><code>uvx shotgun-sh@latest</code></pre>

<p>⚡ Takes 30 seconds to install.<br>
🤠 Join the posse on <a href="https://discord.com/invite/5RmY6J2N7s">Discord</a> to share what you build.</p>

</div>

---

**License:** MIT | **Python:** 3.11+ | **Homepage:** [shotgun.sh](https://shotgun.sh/)
