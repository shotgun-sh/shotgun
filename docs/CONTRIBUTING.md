# Contributing to Shotgun

Thank you for your interest in contributing to Shotgun! This guide will help you get started with development.

## Development Setup

### Requirements

- **Python 3.11+** (3.13 recommended)
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

## Development Commands

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

## Code Coverage

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

**Coverage Requirements:**
- PRs must maintain 70%+ code coverage (excluding cli/tui folders)
- New features should include comprehensive tests
- Bug fixes should include regression tests

## Python Version Management

The project supports **Python 3.11+**. The `.python-version` file specifies Python 3.11 to ensure development against the minimum supported version.

If using **pyenv**:
```bash
pyenv install 3.11
```

If using **uv** (recommended):
```bash
uv python install 3.11
uv sync --python 3.11
```

## Commit Message Convention

This project enforces **Conventional Commits** specification. All commit messages must follow this format:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### Required Commit Types

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

### Examples

```bash
feat: add user authentication system
fix: resolve memory leak in data processing
docs: update API documentation
refactor: simplify user validation logic
```

### Commit with Scope

```bash
feat(auth): implement OAuth2 integration
fix(api): handle null responses properly
docs(readme): add installation instructions
```

### Breaking Changes

For breaking changes, add `!` after the type/scope:

```bash
feat!: remove deprecated API endpoints
fix(auth)!: change authentication flow
```

### Interactive Commit Creation

```bash
uv run cz commit
```

## Contributing Workflow

1. **Fork the repository**

2. **Create a feature branch** following the naming convention:
   ```bash
   git checkout -b feat/feature-name
   git checkout -b fix/bug-name
   git checkout -b docs/documentation-update
   ```

3. **Make your changes**
   - Write clear, concise code
   - Add tests for new functionality
   - Update documentation as needed
   - Follow the existing code style

4. **Run the pre-commit hooks**:
   ```bash
   uv run lefthook run pre-commit
   ```

5. **Commit with conventional format**:
   ```bash
   git commit -m "feat: add new feature"
   ```

6. **Push to your fork**:
   ```bash
   git push origin feat/feature-name
   ```

7. **Create a Pull Request**
   - Use conventional commit format for PR title
   - Provide clear description of changes
   - Reference any related issues
   - Ensure all CI checks pass

## Pull Request Guidelines

### PR Title Format

PR titles MUST follow the Conventional Commits format. When using "Squash and merge", GitHub will use the PR title as the commit message.

**Valid PR Title Examples:**
```
feat: implement user dashboard
fix: resolve login session timeout issue
docs: add contributing guidelines
refactor: restructure project components
```

### PR Description

Your PR description should include:
- **Summary**: Brief overview of the changes
- **Changes**: Bullet-point list of specific modifications
- **Test Plan**: How you tested the changes
- **Related Issues**: Links to related issues/discussions

### Before Submitting

- [ ] Code follows project style guidelines
- [ ] Tests added/updated and passing
- [ ] Documentation updated
- [ ] Coverage requirements met (70%+)
- [ ] Conventional commit format used
- [ ] All CI checks passing

## Code Style Guidelines

- Use **Pydantic Models** instead of dicts or dataclasses when possible
- Follow **PEP 8** style guidelines
- Use **type hints** for all function signatures
- Write **docstrings** for public functions and classes
- Keep functions focused and concise
- Use meaningful variable names

## Testing Guidelines

- Use **pytest** for all tests
- Write tests as separate functions, not pytest classes
- Don't write assertions for log messages (they change frequently)
- Include edge cases and error scenarios
- Aim for high code coverage (70%+ required)
- Use mocking for external dependencies

## Git Hooks

Git hooks are automatically installed and run on commit. See [Git Hooks Documentation](GIT_HOOKS.md) for detailed information about:
- Lefthook configuration
- Secret scanning with trufflehog
- Linting and formatting checks
- Type checking
- Commit message validation

## CI/CD

See [CI/CD Documentation](CI_CD.md) for information about:
- GitHub Actions workflows
- Automated testing
- Code quality checks
- Deployment process

## Need Help?

- Join our [Discord community](https://discord.gg/5RmY6J2N7s)
- Check existing [GitHub Issues](https://github.com/shotgun-sh/shotgun/issues)
- Review [Documentation](https://github.com/shotgun-sh/shotgun/tree/main/docs)

## License

By contributing to Shotgun, you agree that your contributions will be licensed under the MIT License.
