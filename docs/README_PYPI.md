# Shotgun

**Spec-Driven Development for AI Code Generation**

Shotgun is a CLI tool that turns work with AI code-gen tools from "I want to build X" into: **research → specs → plans → tasks → implementation**. It reads your entire codebase, coordinates AI agents to do the heavy lifting, and exports clean artifacts in the agents.md format so your code-gen tools actually know what they're building.

🌐 **Learn more at [shotgun.sh](https://shotgun.sh/)**

## Features

### 📊 Complete Codebase Understanding

Before writing a single line, Shotgun reads all of it. Your patterns. Your dependencies. Your technical debt. Whether you're adding features, onboarding devs, planning migrations, or refactoring - Shotgun knows what you're working with.

### 🔄 Five Modes. One Journey. Zero Gaps.

**Research** (what exists) → **Specify** (what to build) → **Plan** (how to build) → **Tasks** (break it down) → **Export** (to any tool)

Not another chatbot. A complete workflow where each mode feeds the next.

### ➡️ Export to agents.md

Outputs plug into many code-generation tools including Codex, Cursor, Warp, Devin, opencode, Jules, and more.

### 📝 Specs That Don't Die in Slack

Every research finding, every architectural decision, every "here's why we didn't use that library" - captured as markdown in your repo. Version controlled. Searchable.

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

If you don't have `uv` installed, get it at [astral.sh/uv](https://astral.sh/uv) or `curl -LsSf https://astral.sh/uv/install.sh | sh`

## Quick Start

```bash
# Research your codebase or a topic
shotgun research "What is our authentication flow?"

# Generate specifications
shotgun spec "Add OAuth2 authentication"

# Create an implementation plan
shotgun plan "Build user dashboard"

# Break down into tasks
shotgun tasks "Implement payment system"

# Export to agents.md format for your code-gen tools
shotgun export
```

## Support

Have questions? Join our community on **[Discord](https://discord.gg/5RmY6J2N7s)**

---

**License:** MIT
**Python:** 3.11+
