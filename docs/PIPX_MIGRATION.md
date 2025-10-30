# Migrating from pipx to uvx

## Why We're Switching

We've switched from recommending `pipx` to `uvx` as the primary installation method for shotgun-sh. This change solves critical installation issues that many users were experiencing.

## The Problem with pipx

Users installing shotgun-sh via pipx were encountering build failures:

```bash
pipx install shotgun-sh
# Error: /bin/sh: cmake: command not found
# Error: subprocess.CalledProcessError: Command '['make', 'clean']' returned non-zero exit status 2.
```

This happens because:
1. shotgun-sh depends on `kuzu`, a graph database with native extensions
2. Pre-built binary wheels exist for kuzu on all major platforms
3. **However, pip/pipx sometimes falls back to building from source** instead of using the binary wheels
4. Building from source requires `cmake`, `make`, and C++ compilers - tools most users don't have installed

## Why uvx Solves This

With `uvx` (part of the `uv` tool), we can enforce binary-only installation through configuration:

```toml
[tool.uv.pip]
only-binary = ["kuzu"]
```

This means:
- ✅ **No build tools required** - uv will ONLY use pre-built binary wheels
- ✅ **10-100x faster** - uv's resolver is dramatically faster than pip
- ✅ **Better reliability** - If no binary wheel exists, it fails fast with a clear error
- ✅ **Modern tooling** - Part of the Astral ecosystem (creators of ruff)

## How to Migrate

### Step 1: Uninstall the pipx version

```bash
pipx uninstall shotgun-sh
```

### Step 2: Install uv

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Or with Homebrew:**
```bash
brew install uv
```

**Windows:**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Step 3: Run shotgun-sh with uvx

**Ephemeral (no installation):**
```bash
uvx shotgun-sh@latest
```

**Or install permanently:**
```bash
uv tool install shotgun-sh
```

Then just run:
```bash
shotgun
```

## Benefits of uvx

1. **No cmake/build errors** - Binary wheels enforced, no compilation needed
2. **10-100x faster installation** - uv's resolver is incredibly fast
3. **Automatic updates** - Works with our auto-update system
4. **Smaller footprint** - uv manages environments more efficiently
5. **Future-proof** - Aligns with modern Python packaging standards

## Need Help?

- 💬 **Get support**: Join our [Discord](https://discord.gg/5RmY6J2N7s)
- 📖 **Documentation**: Visit [shotgun.sh](https://shotgun.sh)
- 🐙 **GitHub Issues**: [Report a problem](https://github.com/shotgun-sh/shotgun-alpha/issues)

## FAQ

**Q: Can I keep using pipx?**
A: Yes, pipx still works as a fallback, but you may encounter the cmake build errors. We strongly recommend switching to uvx.

**Q: Will my data be preserved?**
A: Yes! Your shotgun data (in `~/.shotgun-sh/`) is completely separate from how the tool is installed.

**Q: Do I need to uninstall pipx?**
A: No, you can keep pipx installed for other tools. Just uninstall shotgun-sh from pipx.

**Q: Is uvx safe?**
A: Yes! `uv` is created by Astral, the company behind ruff (the popular Python linter). It's open source and widely adopted in the Python community.

---

*Last updated: 2025-10-28*
