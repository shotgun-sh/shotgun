# Shotgun

A Python CLI tool for research, planning, and task management powered by AI agents.

## Features

- **Research**: Perform research with agentic loops
- **Planning**: Generate structured plans for achieving goals
- **Tasks**: Generate prioritized task lists with agentic approaches

## Installation

### From PyPI (Recommended)

```bash
pip install shotgun-sh
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

If installed from PyPI, simply use:
```bash
shotgun --help
```

### Virtual Environment Setup (Optional)

If you prefer using a local virtual environment:

```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv sync --all-extras
shotgun --help
```

## Usage

### Using Direct Commands (after uv sync)

```bash
# Research a topic
shotgun research "What is quantum computing?"

# Generate a plan
shotgun plan "Build a web application"
shotgun plan "build me a house"

# Generate tasks for a project
shotgun tasks "Create a machine learning model"
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
- **pipx**: `pipx upgrade shotgun-sh`
- **pip**: `pip install --upgrade shotgun-sh`
- **venv**: Updates within the virtual environment

## Development Setup

### Requirements

- **Python 3.10+** (3.13 recommended)
- **uv** - Fast Python package installer and resolver
- **actionlint** (optional) - For GitHub Actions workflow validation

### Quick Start

1. **Clone and setup**:
   ```bash
   git clone https://github.com/shotgun-sh/shotgun.git
   cd shotgun
   ```

2. **Install uv** (if not already installed):
   ```bash
   # macOS/Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # Or via brew
   brew install uv
   ```

3. **Install dependencies**:
   ```bash
   uv sync --all-extras
   ```

4. **Install git hooks**:
   ```bash
   uv run lefthook install
   ```

5. **Verify setup**:
   ```bash
   uv run shotgun --version
   ```

### Development Commands

```bash
# Run the CLI
uv run shotgun --help

# Run the TUI
uv run tui

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=src --cov-report=term-missing --cov-report=html

# Run linting
uv run ruff check .

# Run formatting
uv run ruff format .

# Run type checking
uv run mypy src/

# Run all pre-commit hooks manually
uv run lefthook run pre-commit
```

### Code Coverage

To analyze test coverage and identify areas that need testing:

```bash
# Run tests with coverage analysis
uv run pytest --cov=src --cov-report=term-missing --cov-report=html
```

This will:
- Display coverage summary in the terminal
- Generate a detailed HTML coverage report

**Viewing the coverage report:**
Open `htmlcov/index.html` in your browser to see:
- Overall coverage percentage
- File-by-file coverage breakdown  
- Line-by-line coverage highlighting
- Missing coverage areas

The coverage configuration is in `pyproject.toml` and will automatically run when you use `uv run pytest`.

### Git Hooks (Lefthook)

This project uses [lefthook](https://github.com/evilmartians/lefthook) for git hooks. The hooks automatically run:

- **ruff** - Python linting with auto-fix
- **ruff-format** - Code formatting  
- **mypy** - Type checking
- **commitizen** - Commit message validation
- **actionlint** - GitHub Actions workflow validation (if installed)

#### Installing actionlint (recommended)

```bash
# macOS
brew install actionlint

# Linux/macOS (direct download)
curl -sSfL https://raw.githubusercontent.com/rhysd/actionlint/main/scripts/download-actionlint.bash | bash

# Go install
go install github.com/rhysd/actionlint/cmd/actionlint@latest
```


### Python Version Management

The project supports **Python 3.10+**. The `.python-version` file specifies Python 3.10 to ensure development against the minimum supported version.

If using **pyenv**:
```bash
pyenv install 3.10.16  # or latest 3.10.x
```

If using **uv** (recommended):
```bash
uv python install 3.10
uv sync --python 3.10
```

### Commit Message Convention

This project enforces **Conventional Commits** specification. All commit messages must follow this format:

```
<type>[optional scope]: <description>
```

**Required commit types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code formatting changes
- `refactor`: Code restructuring without feature changes
- `perf`: Performance improvements
- `test`: Adding or updating tests
- `build`: Build system changes
- `ci`: CI/CD changes
- `chore`: Maintenance tasks
- `revert`: Reverting previous commits

**Examples:**
```bash
feat: add user authentication system
fix: resolve memory leak in data processing
docs: update API documentation
refactor: simplify user validation logic
```

**For interactive commit creation:**
```bash
uv run cz commit
```

### Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/feature-name`
3. Make your changes
4. Run the pre-commit hooks: `uv run lefthook run pre-commit`
5. Commit with conventional format: `git commit -m "feat: add new feature"`
6. Push to your fork: `git push origin feat/feature-name`
7. Create a Pull Request with conventional title format

### CI/CD

GitHub Actions automatically:
- Runs on pull requests and pushes to main
- Tests with Python 3.10
- Validates code with ruff, ruff-format, and mypy
- Ensures all checks pass before merge

## Observability & Telemetry

Shotgun includes built-in observability with Sentry for error tracking and Logfire for logging and tracing. Both services track users anonymously using a UUID generated on first run.

### Anonymous User Tracking

Each user gets a unique anonymous ID stored in their config:
```bash
# Get your anonymous user ID
shotgun config get-user-id
```

This ID is automatically included in:
- **Sentry**: Error reports and exceptions
- **Logfire**: All logs, traces, and spans

### Logfire Queries

Logfire uses SQL for querying logs. Here are helpful queries for debugging and analysis:

#### Find all logs for a specific user
```sql
SELECT * FROM records
WHERE attributes->>'user_id' = 'your-user-id-here'
ORDER BY timestamp DESC;
```

#### Track user actions
```sql
SELECT
  timestamp,
  span_name,
  message,
  attributes
FROM records
WHERE attributes->>'user_id' = 'your-user-id-here'
  AND span_name LIKE '%research%'
ORDER BY timestamp DESC;
```

#### Find slow operations for a user
```sql
SELECT
  span_name,
  duration_ms,
  attributes
FROM records
WHERE attributes->>'user_id' = 'your-user-id-here'
  AND duration_ms > 1000
ORDER BY duration_ms DESC;
```

#### Find errors for a user
```sql
SELECT * FROM records
WHERE attributes->>'user_id' = 'your-user-id-here'
  AND level = 'error'
ORDER BY timestamp DESC;
```

#### Analyze user's AI provider usage
```sql
SELECT
  attributes->>'provider' as provider,
  COUNT(*) as usage_count,
  AVG(duration_ms) as avg_duration
FROM records
WHERE attributes->>'user_id' = 'your-user-id-here'
  AND attributes->>'provider' IS NOT NULL
GROUP BY provider;
```

#### Track feature usage by user
```sql
SELECT
  span_name,
  COUNT(*) as usage_count
FROM records
WHERE attributes->>'user_id' = 'your-user-id-here'
  AND span_name IN ('research', 'plan', 'tasks')
GROUP BY span_name
ORDER BY usage_count DESC;
```

### Setting Up Observability (Optional)

For local development with Logfire:
```bash
# Set environment variables
export LOGFIRE_ENABLED=true
export LOGFIRE_TOKEN=your-logfire-token

# Run shotgun - will now send logs to Logfire
shotgun research "topic"
```

For Sentry (automatically configured in production builds):
```bash
# Set for local development
export SENTRY_DSN=your-sentry-dsn
```

### Privacy

- **No PII collected**: Only anonymous UUIDs are used for identification
- **Opt-in for development**: Telemetry requires explicit environment variables
- **Automatic in production**: Production builds include telemetry for error tracking

## Support

Join our discord https://discord.gg/5RmY6J2N7s
