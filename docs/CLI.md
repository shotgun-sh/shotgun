# Shotgun CLI Usage

While the interactive TUI is the recommended way to use Shotgun, CLI commands are available for scripting and automation.

## Run Command

Execute prompts using the Router agent in drafting mode (auto-executes without confirmation):

```bash
shotgun run "your prompt here"
```

### Options

| Flag | Description |
|------|-------------|
| `-n`, `--non-interactive` | Disable user interaction (for CI/CD) |
| `-p`, `--provider` | AI provider to use (openai, anthropic, google) |

### Examples

```bash
# Research and plan in one go
shotgun run "Research OAuth2 best practices and create an implementation plan"

# Non-interactive mode for CI/CD
shotgun run -n "What authentication methods does this codebase use?"

# Use a specific provider
shotgun run -p anthropic "Analyze the database schema and suggest optimizations"
```

The Router agent automatically orchestrates the appropriate sub-agents (Research, Specify, Plan, Tasks, Export) based on your prompt.

## Utility Commands

### Context Analysis
```bash
shotgun context                    # View token usage
shotgun context --format json      # JSON output
shotgun context --format markdown  # Markdown output
```

### Conversation Management
```bash
shotgun clear    # Clear conversation history
shotgun compact  # Compress history while preserving context
```

### Configuration
```bash
shotgun config                                    # View config
shotgun config set openai --api-key "your-key"   # Set API key
shotgun config set anthropic --api-key "your-key"
```

### Codebase Management
```bash
shotgun codebase index    # Build codebase graph
shotgun codebase info     # View graph statistics
```

## Output Files

Output is written to `.shotgun/`:

| File | Content |
|------|---------|
| `.shotgun/research.md` | Research findings |
| `.shotgun/specification.md` | Feature specifications |
| `.shotgun/plan.md` | Implementation plans |
| `.shotgun/tasks.md` | Task breakdowns |
| `.shotgun/AGENTS.md` | Export for AI agents |

## Scripting Example

```bash
#!/bin/bash
# Automated spec generation
shotgun run -n "Research $1 and create a specification with implementation plan"
```

## Why Use the TUI Instead?

The TUI provides visual feedback, natural conversation flow, mode switching, and keyboard shortcuts. **Use the TUI for daily work, CLI for automation.**

```bash
shotgun --help      # View all commands
shotgun run --help  # Run command help
```

---

**For interactive usage, see the main [README.md](../README.md)**.
