# Claude Code Instructions for Shotgun

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

### Examples of Valid Commit Messages

```
feat: add user authentication system
fix: resolve memory leak in data processing
docs: update API documentation for v2.0
style: format code according to black standards
refactor: simplify user validation logic
perf: optimize database queries for user lookup
test: add unit tests for authentication module
build: update dependencies to latest versions
ci: add automated deployment pipeline
chore: update gitignore for Python cache files
revert: revert feat: add experimental feature
```

### Commit Message with Scope

```
feat(auth): implement OAuth2 integration
fix(api): handle null responses properly
docs(readme): add installation instructions
```

### Breaking Changes

For breaking changes, add `!` after the type/scope:

```
feat!: remove deprecated API endpoints
fix(auth)!: change authentication flow
```

## Pull Request Title Convention

PR titles MUST also follow the Conventional Commits format. When using "Squash and merge", GitHub will use the PR title as the commit message.

### Valid PR Title Examples

```
feat: implement user dashboard
fix: resolve login session timeout issue
docs: add contributing guidelines
refactor: restructure project components
```

### Tests

- Tests must use pytest and must be seperate functions, not a pytest class.

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