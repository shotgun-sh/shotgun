# CI/CD Documentation

Shotgun uses GitHub Actions for continuous integration and continuous deployment. This document explains the automated workflows and checks.

## Overview

GitHub Actions automatically run on:
- **Pull requests** to main branch
- **Pushes** to main branch
- **Tags** for releases

## Automated Workflows

### Pull Request Checks

When you open a pull request, the following checks run automatically:

#### 1. Code Quality Checks

- **Ruff Linting** - Checks Python code for style and potential bugs
- **Ruff Format** - Verifies code is properly formatted
- **Mypy** - Static type checking for type safety

#### 2. Testing

- **Pytest** - Runs full test suite
- **Coverage** - Ensures 70%+ code coverage (excluding cli/tui directories)

#### 3. Security Checks

- **Trufflehog** - Scans for secrets and credentials
- **Actionlint** - Validates GitHub Actions workflow files

#### 4. Commit Message Validation

- **Conventional Commits** - Ensures PR title follows conventional commit format

### Supported Python Versions

Tests run on:
- **Python 3.11** (minimum supported version)
- **Python 3.13** (recommended version)

### Operating Systems

Tests run on:
- **Ubuntu Latest** (Linux)
- **macOS Latest** (macOS)
- **Windows Latest** (Windows)

## Required Checks

Before a PR can be merged, all of these must pass:

- ✅ All tests passing
- ✅ Code coverage ≥ 70%
- ✅ Linting passes (ruff)
- ✅ Formatting correct (ruff format)
- ✅ Type checking passes (mypy)
- ✅ No secrets detected (trufflehog)
- ✅ Conventional commit title format
- ✅ All GitHub Actions workflows valid

## Workflow Files

### `.github/workflows/pr.yml`

Runs on pull requests:
- Installs dependencies with `uv`
- Runs all code quality checks
- Executes test suite with coverage
- Validates commit messages
- Scans for secrets

### `.github/workflows/publish.yml`

Runs on version tags (e.g., `v0.1.0`):
- Builds Python package
- Publishes to PyPI
- Creates GitHub release
- Builds and pushes Docker image

### `.github/workflows/docker.yml`

Runs on main branch pushes and tags:
- Builds Docker image
- Pushes to GitHub Container Registry
- Tags with version and `latest`

### `.github/workflows/test-installation.yml`

Runs daily to verify installation methods work:
- Tests `uvx shotgun-sh@latest` installation
- Tests `uv tool install shotgun-sh`
- Ensures package is installable from PyPI

## Local CI Testing

### Run All Checks Locally

Before pushing, run all checks locally:

```bash
# Run pre-commit hooks (includes most checks)
uv run lefthook run pre-commit

# Run tests with coverage
uv run pytest --cov=src --cov-report=term-missing --cov-report=html

# Verify coverage meets threshold
uv run pytest --cov=src --cov-fail-under=70
```

### Individual Check Commands

```bash
# Linting
uv run ruff check .

# Formatting
uv run ruff format --check .

# Type checking
uv run mypy src/

# Run tests
uv run pytest

# Coverage report
uv run pytest --cov=src --cov-report=html
open htmlcov/index.html

# Secret scanning
trufflehog git file://. --since-commit HEAD --exclude-globs=uv.lock

# Validate workflows
actionlint .github/workflows/*.yml
```

## Coverage Requirements

### Coverage Threshold

PRs must maintain **70% code coverage** or higher.

### What's Excluded

The following directories are excluded from coverage requirements:
- `src/shotgun/cli/` - Command-line interface
- `src/shotgun/tui/` - Terminal user interface

These are excluded because:
- UI code is difficult to test programmatically
- They are thin wrappers around core functionality
- Core functionality (which has tests) is what matters

### Viewing Coverage Reports

After running tests with coverage:

```bash
# Terminal report
uv run pytest --cov=src --cov-report=term-missing

# HTML report
uv run pytest --cov=src --cov-report=html
open htmlcov/index.html
```

The HTML report shows:
- Overall coverage percentage
- File-by-file breakdown
- Line-by-line highlighting
- Missing coverage areas

## Deployment Process

### PyPI Publishing

Automated on version tags:

1. Create and push a version tag:
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```

2. GitHub Actions automatically:
   - Builds the package with `hatch`
   - Embeds telemetry keys at build time
   - Publishes to PyPI
   - Creates GitHub release

### Docker Publishing

Automated on main branch pushes and tags:

1. On push to main:
   - Builds Docker image
   - Tags as `:dev`
   - Pushes to ghcr.io

2. On version tag:
   - Builds Docker image
   - Tags as `:latest` and `:v0.1.0`
   - Pushes to ghcr.io

## Secrets and Environment Variables

### Required GitHub Secrets

The following secrets must be configured in GitHub repository settings:

- `PYPI_API_TOKEN` - For PyPI publishing
- `SHOTGUN_SENTRY_DSN` - Sentry error tracking (embedded at build time)
- `SHOTGUN_LOGFIRE_TOKEN` - Logfire logging (embedded at build time)
- `SHOTGUN_POSTHOG_API_KEY` - PostHog analytics (embedded at build time)
- `SHOTGUN_POSTHOG_PROJECT_ID` - PostHog project ID (embedded at build time)

### Build-Time Secrets

Telemetry secrets are embedded at build time via Hatch build hooks:
- Only included in production builds (PyPI, Docker)
- Not present in source code
- Read from environment variables during build
- Cannot be changed after build

## Troubleshooting CI Failures

### Linting Failures

If ruff check fails:

```bash
# Auto-fix issues
uv run ruff check --fix .

# Check remaining issues
uv run ruff check .
```

### Formatting Failures

If ruff format fails:

```bash
# Auto-format code
uv run ruff format .
```

### Type Checking Failures

If mypy fails:

```bash
# Run mypy locally
uv run mypy src/

# Check specific file
uv run mypy src/shotgun/specific_file.py
```

Add type hints or use `# type: ignore` comments for legitimate issues.

### Test Failures

If pytest fails:

```bash
# Run tests locally
uv run pytest

# Run specific test
uv run pytest test/unit/test_specific.py

# Run with verbose output
uv run pytest -v

# Show stdout/stderr
uv run pytest -s
```

### Coverage Failures

If coverage is below 70%:

```bash
# Generate coverage report
uv run pytest --cov=src --cov-report=html

# Open report to see missing coverage
open htmlcov/index.html

# Add tests for uncovered code
```

### Secret Scanning Failures

If trufflehog detects a secret:

1. **Verify it's a real secret** (not a false positive)
2. **Remove the secret** from the code
3. **Rotate the secret** if it was committed
4. **Use environment variables** for secrets
5. **Never commit** credentials to the repository

If it's a false positive, update `.trufflehog-exclude.txt` or hook configuration.

### Commit Message Failures

If commit message validation fails:

PR title must follow conventional commits format:

```bash
# Valid formats
feat: add new feature
fix: resolve bug
docs: update documentation
refactor: restructure code
test: add tests
ci: update workflows
chore: update dependencies

# With scope
feat(auth): add OAuth support
fix(api): handle null values
```

## Manual Workflow Triggers

Some workflows can be triggered manually:

```bash
# Trigger workflow from GitHub UI
# 1. Go to Actions tab
# 2. Select workflow
# 3. Click "Run workflow"
# 4. Choose branch and parameters
```

## Performance Optimization

### Cache Usage

GitHub Actions caches:
- Python dependencies (via uv)
- pytest cache
- mypy cache
- ruff cache

This speeds up subsequent runs significantly.

### Parallel Jobs

Tests run in parallel across:
- Different Python versions
- Different operating systems
- Different test suites

This provides fast feedback while ensuring compatibility.

## Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [PyPI Publishing](https://packaging.python.org/en/latest/tutorials/packaging-projects/)
- [GitHub Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)

## Support

If you encounter CI/CD issues:

- Check workflow logs in GitHub Actions tab
- Review error messages carefully
- Test locally first with same commands
- Ask in [Discord community](https://discord.gg/5RmY6J2N7s)
- Open an issue if it's a CI/CD bug
