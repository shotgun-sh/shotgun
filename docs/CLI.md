# Shotgun CLI Usage

While the interactive TUI is the recommended way to use Shotgun, CLI commands are available for scripting, automation, and quick one-off tasks.

## CLI Commands

### Direct Mode Commands

Run specific modes directly from the command line:

```bash
# Research mode
shotgun research "your question or research topic"

# Specify mode
shotgun spec "your feature specification"

# Plan mode
shotgun plan "your implementation plan request"

# Tasks mode
shotgun tasks "your task breakdown request"

# Export mode
shotgun export "optional: specific export instructions"
```

### Examples

#### Research Mode
```bash
shotgun research "how do we handle authentication in this codebase?"
shotgun research "best practices for implementing real-time collaboration"
shotgun research "what database libraries are we using?"
```

#### Specify Mode
```bash
shotgun spec "Add OAuth2 authentication with refresh token support"
shotgun spec "User profile management system with avatar uploads"
shotgun spec "Real-time notification system with WebSockets"
```

#### Plan Mode
```bash
shotgun plan "Build user dashboard with analytics widgets"
shotgun plan "Migrate authentication system to OAuth2"
shotgun plan "Implement payment processing with Stripe"
```

#### Tasks Mode
```bash
shotgun tasks "Create the tasks for implementing the OAuth2 system"
shotgun tasks "Break down the user dashboard plan into tasks"
shotgun tasks "Generate implementation tasks for the payment system"
```

#### Export Mode
```bash
shotgun export
shotgun export "Create a PRD for the authentication feature"
shotgun export "Generate AGENTS.md for the payment system"
```

## Utility Commands

### Context Analysis
View token usage and conversation statistics:

```bash
shotgun context
shotgun context --format json
shotgun context --format markdown
```

### Conversation Management

#### Clear Conversation
Start fresh with a new conversation:

```bash
shotgun clear
```

#### Compact Conversation
Compress conversation history while preserving context:

```bash
shotgun compact
```

### Configuration

#### View Configuration
```bash
shotgun config
```

#### Update API Keys
```bash
shotgun config --provider anthropic --api-key "your-key"
shotgun config --provider openai --api-key "your-key"
shotgun config --provider gemini --api-key "your-key"
```

#### Update Model Selection
```bash
shotgun config --model "claude-sonnet-4"
shotgun config --model "gpt-4"
shotgun config --model "gemini-2.0-flash-exp"
```

### Codebase Graph Management

#### Build Codebase Graph
```bash
shotgun index
```

#### Reindex Codebase
```bash
shotgun reindex
```

#### View Graph Statistics
```bash
shotgun graph-info
```

## Output Files

Each mode writes to its own file in `.shotgun/`:

| Mode | Output File |
|------|-------------|
| Research | `.shotgun/research.md` |
| Specify | `.shotgun/specification.md` |
| Plan | `.shotgun/plan.md` |
| Tasks | `.shotgun/tasks.md` |
| Export | `.shotgun/AGENTS.md`, `.shotgun/PRD.md`, etc. |

## Scripting and Automation

CLI commands are useful for:

- **CI/CD Integration:** Generate specs as part of your pipeline
- **Git Hooks:** Automatically research changes before commits
- **Scripting:** Batch process multiple research requests
- **Automation:** Integrate Shotgun into your development workflow

### Example: Pre-commit Research Script

```bash
#!/bin/bash
# .git/hooks/pre-commit

# Get list of modified files
MODIFIED_FILES=$(git diff --cached --name-only --diff-filter=ACM)

# Research the changes
shotgun research "Analyze the impact of these changes: ${MODIFIED_FILES}"
```

### Example: Automated Spec Generation

```bash
#!/bin/bash
# generate-specs.sh

# Read feature descriptions from file
while IFS= read -r feature; do
  echo "Generating spec for: $feature"
  shotgun spec "$feature"
  shotgun plan "Plan for: $feature"
  shotgun tasks "Tasks for: $feature"
done < features.txt
```

## Environment Variables

Optional environment variables for advanced configuration:

```bash
# Configuration paths (optional)
export SHOTGUN_CONFIG_PATH="~/.shotgun-sh/config.json"
export SHOTGUN_DATA_DIR="~/.shotgun-sh"
```

**Note:** API keys are managed through the `shotgun config` command, not environment variables.

## Why Use the TUI Instead?

While CLI commands work well for automation, the TUI provides:

- **Visual feedback:** See progress, status, and mode indicators in real-time
- **Natural conversation:** Chat naturally without constructing command-line arguments
- **Mode switching:** Easily switch between modes without new commands
- **Context awareness:** Visual display of conversation history and state
- **Keyboard shortcuts:** Quick access to common operations
- **Better UX:** Designed for interactive development workflows

**Recommendation:** Use the TUI for daily development work, and CLI commands for automation and scripting.

## Getting Help

```bash
shotgun --help
shotgun research --help
shotgun spec --help
shotgun plan --help
shotgun tasks --help
shotgun export --help
```

---

**For interactive usage, see the main [README.md](../README.md)**.
