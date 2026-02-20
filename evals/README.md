# Shotgun Evaluation System

Evaluation framework for testing Shotgun agent behaviors deterministically.

## Quick Start

```bash
# Run the router smoke test with a specific model
uv run python -m evals.runner --suite router_smoke --model claude-opus-4-6

# Run without LLM judge (faster, deterministic only)
uv run python -m evals.runner --suite router_smoke --model claude-opus-4-6 --no-judge

# Run a single test case
uv run python -m evals.runner --case vague_prompt_clarifying_questions --model claude-opus-4-6

# Compare multiple models
uv run python -m evals.runner --suite router_smoke --model claude-opus-4-6 --model gpt-5.1 --model gemini-3.1-pro-preview
```

## Output Formats

```bash
# Console output (default)
--report console

# JSON output
--report json

# Both
--report both

# Save to file
--report json --out evals/reports/results.json
```

## Architecture

```
evals/
├── datasets/                    # Test case definitions
│   └── router_agent/
│       └── clarifying_questions_cases.py
├── evaluators/
│   └── deterministic/
│       └── router_evaluators.py  # Rule-based evaluators
├── judges/                       # LLM-as-judge evaluators
├── executor.py                   # Runs agents and captures output
├── runner.py                     # CLI entry point
└── models.py                     # Pydantic models
```

## Current Test Cases

### `vague_prompt_clarifying_questions`

Tests that the Router agent asks clarifying questions when given a vague prompt like "I want to add a new feature to this project".

**Expected behavior:** Router should populate `AgentResponse.clarifying_questions` with at least 1 question before taking action.

## Evaluators

### Deterministic Evaluators

| Evaluator | Severity | Description |
|-----------|----------|-------------|
| `disallowed_tool_usage` | HARD | Fails if Router uses file/code execution tools |
| `execution_failure` | HARD | Fails if agent crashes or returns empty response |
| `clarifying_questions` | HARD* | Fails if expected questions not asked (*when `expect_clarifying_questions=True`) |
| `expected_tool_presence` | SOFT | Checks expected tools were used |
| `content_assertion` | SOFT | Checks response contains/excludes keywords |
| `delegation_correctness` | SOFT | Checks Router delegated to expected sub-agent |

### LLM Judge (Optional)

When enabled (default), uses Claude Opus 4.5 to evaluate:
- `delegation_rationale` - Was the delegation decision well-reasoned?
- `context_handling` - Did it preserve user intent?
- `clarity` - Was the response clear?
- `relevance` - Did it address what the user asked?

## Key Design Decisions

1. **TUI Context Simulation**: Evals run with `is_tui_context=True` to get realistic system prompts
2. **Structured Questions**: Tests check `AgentResponse.clarifying_questions` field, not text parsing
3. **HARD vs SOFT Failures**: HARD failures cause immediate test failure; SOFT failures reduce score
4. **Logfire Required**: All eval runs are instrumented with Logfire for debugging

## Environment Variables

Requires `.env` with:
- `SHOTGUN_LOGFIRE_TOKEN` or `LOGFIRE_TOKEN` - For trace capture
- API keys for models being tested (ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.)
