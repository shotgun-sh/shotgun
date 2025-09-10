# Shotgun

A Python CLI tool for research, planning, and task management powered by AI agents.

## Features

- **Research**: Perform research with agentic loops
- **Planning**: Generate structured plans for achieving goals
- **Tasks**: Generate prioritized task lists with agentic approaches

## Installation

### From Source

```bash
git clone https://github.com/shotgun-sh/shotgun.git
cd shotgun
uv sync --all-extras
uv run shotgun --help
```

## Usage

```bash
# Research a topic
uv run shotgun research "What is quantum computing?"

# Generate a plan
uv run shotgun plan "Build a web application"

# Generate tasks for a project
uv run shotgun tasks "Create a machine learning model"
```

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

# Run tests (when available)
uv run pytest

# Run linting
uv run ruff check .

# Run formatting
uv run ruff format .

# Run type checking
uv run mypy src/

# Run all pre-commit hooks manually
uv run lefthook run pre-commit
```

### Git Hooks (Lefthook)

This project uses [lefthook](https://github.com/evilmartians/lefthook) for git hooks. The hooks automatically run:

- **ruff** - Python linting with auto-fix
- **ruff-format** - Code formatting
- **mypy** - Type checking
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

### Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Run the pre-commit hooks: `uv run lefthook run pre-commit`
5. Commit your changes: `git commit -m "Description"`
6. Push to your fork: `git push origin feature-name`
7. Create a Pull Request

### CI/CD

GitHub Actions automatically:
- Runs on pull requests and pushes to main
- Tests with Python 3.10
- Validates code with ruff, ruff-format, and mypy
- Ensures all checks pass before merge

## Support

Join our discord https://discord.gg/5RmY6J2N7s
