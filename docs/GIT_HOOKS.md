# Git Hooks

This project uses [lefthook](https://github.com/evilmartians/lefthook) for git hooks to ensure code quality and security.

## Automated Checks

The hooks automatically run on commit and provide fast feedback:

- **ruff** - Python linting with auto-fix
- **ruff-format** - Code formatting
- **mypy** - Type checking
- **trufflehog** - Secret scanning to prevent committed credentials
- **commitizen** - Commit message validation
- **actionlint** - GitHub Actions workflow validation (if installed)

## Installation

Git hooks are automatically installed when you run:

```bash
uv run lefthook install
```

This should be done as part of the initial development setup. See [CONTRIBUTING.md](CONTRIBUTING.md) for full setup instructions.

## Manual Execution

You can run all pre-commit hooks manually without making a commit:

```bash
uv run lefthook run pre-commit
```

## Secret Scanning with Trufflehog

### Installation (Required)

Trufflehog scans your commits for secrets and API keys before they're pushed to the repository.

**macOS:**
```bash
brew install trufflehog
```

**Linux:**
```bash
curl -sSfL https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/scripts/install.sh | sh -s -- -b /usr/local/bin
```

### Manual Secret Scanning

```bash
# Quick scan: commits since HEAD (excludes uv.lock to avoid false positives)
trufflehog git file://. --since-commit HEAD --exclude-globs=uv.lock

# Full two-pass scan (recommended for comprehensive checking):
# Pass 1: Scan everything except uv.lock
trufflehog git file://. --exclude-globs=uv.lock

# Pass 2: Scan uv.lock only, excluding SentryToken detector
trufflehog git file://. --include-paths=.trufflehog-include-lockfile.txt --exclude-detectors=SentryToken
```

### Two-Pass Scanning Strategy

We use a defense-in-depth approach with two separate scans:

- **Pass 1**: Scans all files except `uv.lock` with all detectors enabled
- **Pass 2**: Scans ONLY `uv.lock` with SentryToken detector disabled

This prevents false positives from Sentry SDK package hashes while still catching any real secrets that might somehow end up in lock files (e.g., credentials in package URLs).

### Why This Matters

Secret scanning prevents:
- Accidentally committing API keys
- Exposing authentication tokens
- Leaking database credentials
- Publishing private keys
- Committing sensitive configuration

If trufflehog finds a potential secret, it will:
1. Block the commit
2. Show you what was detected
3. Give you a chance to remove it before it enters git history

## Actionlint (Recommended)

Actionlint validates GitHub Actions workflow files to catch errors before you push.

### Installation

**macOS:**
```bash
brew install actionlint
```

**Linux/macOS (direct download):**
```bash
curl -sSfL https://raw.githubusercontent.com/rhysd/actionlint/main/scripts/download-actionlint.bash | bash
```

**Go install:**
```bash
go install github.com/rhysd/actionlint/cmd/actionlint@latest
```

### What It Checks

- Syntax errors in workflow files
- Invalid action references
- Type errors in expressions
- Invalid step configurations
- Deprecated GitHub Actions features

## Bypassing Hooks (Not Recommended)

In rare cases, you may need to bypass hooks. Use with caution:

```bash
# Bypass all hooks
LEFTHOOK=0 git commit -m "your message"

# Or use git's built-in flag
git commit --no-verify -m "your message"
```

**Warning:** Bypassing hooks skips:
- Secret scanning (security risk)
- Commit message validation (breaks CI)
- Code formatting (creates inconsistencies)
- Type checking (may introduce bugs)

Only bypass hooks if you have a specific reason and understand the implications.

## Hook Configuration

The hook configuration is defined in `lefthook.yml` at the project root. This file specifies:
- Which hooks to run
- When they run (pre-commit, commit-msg, pre-push, etc.)
- Commands to execute
- File patterns to target

## Troubleshooting

### Hooks Not Running

If hooks aren't running:

```bash
# Reinstall hooks
uv run lefthook install

# Verify installation
uv run lefthook version
```

### Hook Failures

If a hook fails:

1. **Read the error message** - It will tell you what failed
2. **Fix the issue** - Apply the suggested fix
3. **Test manually** - Run the failing command directly
4. **Try again** - Make a new commit

### Slow Hook Performance

If hooks are slow:

- Trufflehog scans can take time on large repos
- First-time mypy checks are slower (subsequent runs use cache)
- Consider running specific tools manually during development

### False Positives in Secret Scanning

If trufflehog detects a false positive:

1. Verify it's actually not a secret
2. Check if it's a test fixture or example
3. If legitimate, add to exclusion patterns in `lefthook.yml`

## Best Practices

- **Don't bypass hooks** unless absolutely necessary
- **Run hooks manually** (`uv run lefthook run pre-commit`) before committing large changes
- **Keep hooks fast** by committing smaller, focused changes
- **Update tools regularly** to get the latest security checks
- **Report issues** if a hook gives incorrect results

## Additional Resources

- [Lefthook Documentation](https://github.com/evilmartians/lefthook)
- [Trufflehog Documentation](https://github.com/trufflesecurity/trufflehog)
- [Actionlint Documentation](https://github.com/rhysd/actionlint)
- [Conventional Commits](https://www.conventionalcommits.org/)
