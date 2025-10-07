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

<img width="600" height="200" alt="Screenshot 2025-08-25 at 4 40 37 PM" src="shotgun_logo.png" />

### Shotgun is a CLI that turns what you want to work on into _research → specs → plans → tasks → implementation_ with full codebase understanding and agents doing the heavy lifting.

<br>
It produces clean, reusable artifacts and exports to the

[agents.md](https://github.com/openai/agents.md)
ecosystem to help you get the most out of code-gen tools and Agents.

<br>

```bash
pipx install shotgun-sh
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
- [Roadmap](#roadmap)
- [FAQ](#faq)
- [Contributing](#contributing)

---

<h2 id="quickstart">Quickstart</h2>

Shotgun is a Python-based CLI tool. We use `pipx` for clean, isolated installation.


> [!WARNING]
> If you tried out an alpha version of shotgun, make sure to uninstall it:\
> `npm uninstall -g @proofs-io/shotgun @proofs-io/shotgun-server`


### Step 1: Install pipx (if you don't have it)

#### macOS

```bash
brew install pipx && pipx ensurepath
```

_No Homebrew? [Install it here](https://brew.sh/)_

#### Linux

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

#### Windows

```bash
python -m pip install --user pipx
python -m pipx ensurepath
```

_Restart your terminal after installation_

### Step 2: Install Shotgun

```bash
pipx install shotgun-sh
```

That's it! 30 seconds and you're ready.

### Step 3: Start Shotgun

Run:

```bash
shotgun
```

**Shotgun will guide you through:**

- Indexing your codebase into a searchable graph
- Setting up your LLM provider (OpenAI, Anthropic, or Gemini)
- Starting your first research session

**Pro tip:** Run Shotgun in your IDE's terminal for the best experience.

---

## What you get today

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

Research (what exists) → Specify (what to build) → Plan (how to build) → Tasks (break it down) → Export (to any tool). Not another chatbot. A complete workflow where each mode feeds the next.

### 📝 **Specs That Don't Die in Slack**

Every research finding, every architectural decision, every "here's why we didn't use that library" - captured as markdown in your repo. Version controlled. Searchable.

---

## Use Cases

- **🚀 Onboarding** - New developer? Shotgun maps your entire architecture and generates docs that actually match the code
- **🔧 Refactoring** - Understand all dependencies before touching anything. Keep your refactor from becoming a rewrite
- **🌱 Greenfield Projects** - Research existing solutions globally before writing line one
- **➕ Adding Features** - Know exactly where your feature fits. Prevent duplicate functionality
- **📦 Migration** - Map the old, plan the new, track the delta. Break migration into safe stages

---

<h2 id="demo">Demo</h2>

**See Shotgun in action**

<p align="center">
  <a href="https://youtu.be/eEUaSaQJBPg">
    <img src="https://github.com/user-attachments/assets/da115b12-7ca5-4bbc-ae20-3684f971b567" alt="Watch the Shotgun demo" width="720" height="450">
  </a>
</p>

**Give Shotgun a spin**

```bash
Onboard me to this codebase.
```

---

<h2 id="roadmap">Roadmap</h2>

### 🚧 Coming soon

- [ ] Token usage display & spend tracking
- [ ] Support for local LLMs
- [ ] Linear agents integration
- [ ] Attachments: add screenshots / PDFs / files to Shotgun
- [ ] Performance improvements (make Shotgun faster)

---

## FAQ

**Q: Does Shotgun collect any stats or data?**  
A: We only gather minimal, anonymous events (e.g., install, server start, tool call). We don’t collect the content itself—only that an event occurred. We use Sentry for error reporting to improve stability.

**Q: Local LLMs?**  
A: Planned. We’ll publish compatibility notes and local provider integrations.

---

<h2 id="contributing">Contributing</h2>
<p>Shotgun is in Beta — we’d love your feedback and support.</p>
<ul>
  <li>Join our <a href="https://discord.com/invite/5RmY6J2N7s"><strong>Discord</strong></a></li>
  <li>Open issues / discussions</li>
  <li>PRs welcome once core is open-sourced</li>
</ul>

<p><em>🚀 We hit #7 on Product Hunt!:</em> 
<a href="https://www.producthunt.com/posts/shotgun"><strong>LINK</strong></a>.  
An upvote, review or comment there helps us reach more builders and gather early feedback.</p>

---

### Uninstall:

```bash
pipx uninstall shotgun-sh
```

### Troubleshooting

**Do you have the old version of Shotgun? (shotgun-alpha)**

Uninstall the shotgun alpha (previous version) by doing the following:

```bash
npm uninstall -g @proofs-io/shotgun --loglevel=error
npm uninstall -g @proofs-io/shotgun-server --loglevel=error
```

---

<div align="center">

  <h2>🚀 Ready to write specs that truly capture your intents?</h2>
<br>
  <p><strong>Research (what exists) → Specify (what to build) → Plan (how to build) → Tasks (break it down) → Export (to any tool). </strong></p>

  <pre><code> pipx install shotgun-sh </code></pre>
  <p>⚡ Takes 30 seconds to install.<br>
  🤠 Join the posse on <a href="https://discord.com/invite/5RmY6J2N7s">Discord</a> to share what you build.</p>

</div>
<br>
<br>
<br>
