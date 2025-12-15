# Claude Code Instructions for Shotgun

## Evals

To understand how to run the evals read evals/README.md

## Commit Message Convention

This project enforces **Conventional Commits** specification. All commit messages MUST follow this format:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### Required Commit Types

**IMPORTANT**: These types must stay in sync between `cz_conventional_commits` (pyproject.toml) and GitHub Actions (pr.yml).

Use these types for your commit messages:

- **feat**: A new feature
- **fix**: A bug fix  
- **docs**: Documentation only changes
- **style**: Changes that don't affect code meaning (formatting, missing semicolons, etc.)
- **refactor**: Code change that neither fixes a bug nor adds a feature
- **perf**: Performance improvements
- **test**: Adding missing tests or correcting existing tests
- **build**: Changes that affect the build system or external dependencies
- **ci**: Changes to CI configuration files and scripts
- **chore**: Other changes that don't modify src or test files
- **revert**: Reverts a previous commit

### Scopes and Breaking Changes

- Add optional scope in parentheses: `feat(auth): implement OAuth2`
- For breaking changes, add `!` after the type/scope: `feat!: remove deprecated API endpoints`

## Pull Request Title Convention

PR titles MUST also follow the Conventional Commits format. When using "Squash and merge", GitHub will use the PR title as the commit message.

### Tests

- Tests must use pytest and must be seperate functions, not a pytest class.

## Testing Policy

### Test Structure

The project has two types of tests:

1. **Unit Tests** (`test/unit/`): Fast, isolated tests with no external dependencies
2. **Integration Tests** (`test/integration/`): Tests that verify complete workflows with real databases

**For Contributors:**
- All tests run in CI/CD for every PR
- Both unit and integration tests must pass
- No API keys required for tests - all external services are mocked

## Commands for Development

- **Install dependencies**: `uv sync --all-extras`
- **Run linting**: `uv run ruff check .`
- **Run formatting**: `uv run ruff format .`
- **Run type checking**: `uv run mypy src/`
- **Create conventional commit**: `uv run cz commit`
- **Validate commit message**: `uv run cz check --commit-msg-file .git/COMMIT_EDITMSG`

## Important Notes

1. Commit message validation is enforced via git hooks (lefthook)
2. PR title validation runs automatically in GitHub Actions
3. Use `uv run cz commit` for interactive commit message creation
4. Breaking changes should be clearly documented in commit body
5. Keep commit messages under 100 characters for the first line
6. Use imperative mood: "add feature" not "added feature"
7. **Claude Code must NEVER bypass validation checks**
8. Code coverage for a PR MUST be 70%+ excluding the cli/tui folders.
9. Don't write tests that assert the logger, thats not useful.
- Always use a Pydantic Model instead of a dict or dataclass when possible.

## Architectural Patterns

### Circular Dependency Resolution

**IMPORTANT**: When encountering circular import issues, use **Protocol-Based Dependency Inversion** instead of workarounds like attribute checking, duck typing with `getattr()`, or `TYPE_CHECKING` blocks with try-except.

#### Example: TUI Protocols

See `src/shotgun/tui/protocols.py` as the canonical example of this pattern.

**Problem**: Components (like `ModeIndicator`, `StatusBar`) need to check screen state (like `qa_mode`, `working`) but importing the concrete screen class (`ChatScreen`) creates circular imports.

**Solution**: Define runtime-checkable protocols that specify the interface:

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class QAStateProvider(Protocol):
    """Protocol for screens that provide Q&A mode state."""

    @property
    def qa_mode(self) -> bool:
        """Whether Q&A mode is currently active."""
        ...

@runtime_checkable
class ProcessingStateProvider(Protocol):
    """Protocol for screens that provide processing state."""

    @property
    def working(self) -> bool:
        """Whether an agent is currently working."""
        ...
```

**Usage in components**:

```python
from shotgun.tui.protocols import QAStateProvider

class ModeIndicator(Widget):
    def render(self) -> str:
        # Check if screen satisfies the protocol
        if isinstance(self.screen, QAStateProvider) and self.screen.qa_mode:
            return "[bold]Q&A mode[/]"
        # ... rest of implementation
```

**Benefits**:
- ✅ Zero circular imports
- ✅ Type-safe with mypy
- ✅ Follows SOLID principles (Dependency Inversion Principle)
- ✅ Self-documenting interfaces
- ✅ Concrete classes automatically satisfy protocols (structural typing)

**When to use**:
1. Component needs to check state/behavior of parent/screen
2. Importing concrete class creates circular dependency
3. Multiple classes may provide the same interface
4. You want type safety without tight coupling

**DO NOT use these workarounds**:
- ❌ `getattr(obj, 'attribute', default)` - loses type safety
- ❌ `hasattr(obj, 'attribute')` - no type checking
- ❌ `TYPE_CHECKING` with try-except `isinstance()` - fails at runtime
- ❌ Moving imports inside functions - hard to maintain

## Logs

Shotgun logs are stored in `~/.shotgun-sh/logs/` with the naming pattern `shotgun-<timestamp>.log`.

- Each TUI session or CLI command creates a new log file
- Timestamp format: `YYYYMMDDTHHMMSSZ` (UTC)
- Example: `shotgun-20251205T131500Z.log`

To view the most recent log:
```bash
ls -t ~/.shotgun-sh/logs/ | head -1 | xargs -I {} cat ~/.shotgun-sh/logs/{}
```

To tail logs from the current session:
```bash
ls -t ~/.shotgun-sh/logs/ | head -1 | xargs -I {} tail -f ~/.shotgun-sh/logs/{}
```

## Conversation History Navigation

### Overview

The shotgun TUI persists conversations to `~/.shotgun-sh/conversation.json`. Understanding this file's structure helps Claude Code quickly search and analyze conversation history.

**Default Location:** `~/.shotgun-sh/conversation.json`
**IMPORTANT:** This is the default path and is almost always where the conversation file is located. Claude Code should assume this path exists and use it directly without asking the user for confirmation.

**Schema Definition:** `src/shotgun/agents/conversation/models.py` (`ConversationHistory` model)
**Persistence Manager:** `src/shotgun/agents/conversation/manager.py` (save/load operations)

### Built-in Analysis Command

The easiest way to analyze conversation context:

```bash
# View token usage breakdown by message type
shotgun context --format markdown

# Get JSON output for programmatic analysis
shotgun context --format json
```

See implementation: `src/shotgun/cli/context.py`

### JSON Structure

```json
{
  "version": 1,
  "agent_history": [...],     // Serialized pydantic_ai ModelMessage objects
  "ui_history": [...],        // ModelMessage + HintMessage objects
  "last_agent_model": "research|specify|plan|tasks|export",
  "updated_at": "2025-10-31T..."
}
```

### Quick Search Patterns with jq

**Finding specific message types:**

```bash
# All user inputs (ModelRequest messages)
jq '.agent_history[] | select(.kind == "request")' ~/.shotgun-sh/conversation.json

# All agent responses (ModelResponse messages)
jq '.agent_history[] | select(.kind == "response")' ~/.shotgun-sh/conversation.json

# All tool calls across the conversation
jq '.agent_history[].parts[]? | select(.kind == "tool-call") | {tool: .tool_name, args: .args}' ~/.shotgun-sh/conversation.json

# Extract all text content from messages
jq '.agent_history[].parts[]? | select(.kind == "text") | .content' ~/.shotgun-sh/conversation.json

# Count messages by type
jq '[.agent_history[] | .kind] | group_by(.) | map({kind: .[0], count: length})' ~/.shotgun-sh/conversation.json

# Get the most recent N messages
jq '.agent_history[-5:]' ~/.shotgun-sh/conversation.json
```

**Searching for specific content:**

```bash
# Find messages containing specific text
jq '.agent_history[] | select(.parts[]?.content? // "" | contains("search term"))' ~/.shotgun-sh/conversation.json

# Find tool calls by tool name
jq '.agent_history[].parts[]? | select(.kind == "tool-call" and .tool_name == "file_read")' ~/.shotgun-sh/conversation.json
```

### Message Types Reference (pydantic_ai)

The conversation uses `pydantic_ai` message types. Understanding these helps with searching:

**Top-level message types:**
- `ModelRequest` - User inputs to the agent (kind: "request")
- `ModelResponse` - Agent responses including tool calls (kind: "response")

**Message part types (in `.parts[]`):**
- `TextPart` - Text content (kind: "text")
- `ToolCallPart` - Tool invocations (kind: "tool-call")
- `ToolReturnPart` - Tool results (kind: "tool-return")
- `UserPromptPart` - User prompt content
- `SystemPromptPart` - System prompts
- `RetryPromptPart` - Retry instructions
- `ThinkingPart` - Model thinking/reasoning content

**Key fields:**
- `message.kind` - Message type identifier
- `part.kind` - Part type identifier
- `part.content` - Text content (TextPart, UserPromptPart)
- `part.tool_name` - Tool name (ToolCallPart)
- `part.args` - Tool arguments (ToolCallPart)

### Schema Details

From `ConversationHistory` model (`src/shotgun/agents/conversation/models.py`):

- **version** (int): Schema version (currently 1)
- **agent_history** (list[SerializedMessage]): Core conversation messages sent to/from agent
- **ui_history** (list[SerializedMessage]): UI-specific messages including `HintMessage` objects
- **last_agent_model** (str): Last active agent type - one of:
  - `research` - Research agent for exploratory tasks
  - `specify` - Specification agent for requirements
  - `plan` - Planning agent for implementation plans
  - `tasks` - Task execution agent
  - `export` - Export agent for deliverables
- **updated_at** (datetime): Last modification timestamp

### Helper Methods

The `ConversationHistory` model provides methods to work with messages:

```python
# In Python code or tests:
from shotgun.agents.conversation import ConversationManager

manager = ConversationManager()  # Uses ~/.shotgun-sh/conversation.json
conversation = await manager.load()

if conversation:
    # Get typed message objects
    agent_messages = conversation.get_agent_messages()  # list[ModelMessage]
    ui_messages = conversation.get_ui_messages()  # list[ModelMessage | HintMessage]

    # Access raw serialized data
    raw_agent = conversation.agent_history  # list[dict]
    raw_ui = conversation.ui_history  # list[dict]
```

### Tips for Claude Code

When asked to analyze or search conversation history:

1. **Start with `shotgun context`** for token/usage analysis
2. **Use `jq` patterns** for specific message searches
3. **Read the schema files** (`conversation/models.py`) for understanding structure
4. **Check message kinds first** - distinguishes between requests/responses/parts
5. **Remember filtering** - `filter_incomplete_messages()` removes corrupted tool calls before saving

## LLM-Friendly Documentation References

Many libraries used in this project provide `llms.txt` or `llms-full.txt` files - condensed documentation optimized for AI coding assistants. Use these when you need to understand how to use a library correctly.

### Core Libraries with llms.txt

- **Pydantic AI** (agent framework - primary AI library)
  - llms.txt: https://ai.pydantic.dev/llms.txt
  - llms-full.txt: https://ai.pydantic.dev/llms-full.txt

- **LiteLLM** (multi-provider LLM gateway)
  - llms.txt: https://docs.litellm.ai/llms.txt

- **Anthropic/Claude** (Claude API documentation)
  - llms.txt: https://docs.anthropic.com/llms.txt

- **Model Context Protocol** (MCP specification)
  - llms.txt: https://modelcontextprotocol.io/llms.txt
  - llms-full.txt: https://modelcontextprotocol.io/llms-full.txt

### Libraries Without llms.txt

These libraries don't have llms.txt files yet. Use their standard documentation:

- **OpenAI SDK**: https://platform.openai.com/docs/api-reference
- **Textual** (TUI framework): https://textual.textualize.io/
- **Kuzu** (graph database): https://docs.kuzudb.com/
- **Logfire** (observability): https://logfire.pydantic.dev/docs/
- **Typer** (CLI framework): https://typer.tiangolo.com/
- **HTTPX** (async HTTP client): https://www.python-httpx.org/