# Shotgun Docker Image

AI-powered CLI tool for research, planning, and task management.

## ⚠️ Important: Use the Stable Release

**Always use the `latest` tag for production use:**

```bash
docker pull ghcr.io/shotgun-sh/shotgun:latest
```

### Why NOT to use `:dev`

**DO NOT use the `:dev` tag unless you are a developer testing new features.**

Development versions:
- ❌ Have telemetry and logging built-in that you probably don't want
- ❌ Never auto-update (you'll be stuck on that version)
- ❌ Are for internal testing only

Production versions (`:latest` and version tags like `:v0.1.0`) are secure and only log anonymous event metadata - no user data is collected.

## Quick Start

**Important:** Always run the container from your code directory so Shotgun can analyze your codebase.

```bash
cd /path/to/your/project

docker run -p 8000:8000 \
  -v $(pwd):/workspace \
  -v ~/.shotgun-sh:/home/shotgun/.shotgun-sh \
  ghcr.io/shotgun-sh/shotgun:latest
```

Access the web interface at **http://localhost:8000**

### What this does:

- Maps port 8000 from the container to your host
- Mounts your current directory as `/workspace` inside the container
- Mounts your Shotgun config directory to persist API keys and settings
- Automatically prompts you to index the codebase on startup

## Available Tags

- **`latest`** - ✅ **Recommended** - Latest stable release (secure, minimal telemetry)
- **`v0.1.0`** - Specific version tags (for pinning to a particular version)
- **`dev`** - ❌ **Not recommended** - Development version with full telemetry (for developers only)

## Custom Port

To use a different port:

```bash
docker run -p 3000:3000 \
  -v $(pwd):/workspace \
  -v ~/.shotgun-sh:/home/shotgun/.shotgun-sh \
  ghcr.io/shotgun-sh/shotgun:latest --port 3000
```

## Background Mode

Run in the background with auto-restart:

```bash
docker run -d --restart unless-stopped \
  --name shotgun-web \
  -p 8000:8000 \
  -v $(pwd):/workspace \
  -v ~/.shotgun-sh:/home/shotgun/.shotgun-sh \
  ghcr.io/shotgun-sh/shotgun:latest
```

Stop the container with:
```bash
docker stop shotgun-web
docker rm shotgun-web
```

## Configuration

On first run, configure your API keys through the web UI at http://localhost:8000. The configuration will persist in the mounted `~/.shotgun-sh` directory.

## Full Documentation

For complete documentation, installation options, and development setup, see the [main README](https://github.com/shotgun-sh/shotgun#readme).

## Support

Join our [Discord community](https://discord.gg/5RmY6J2N7s) for help and discussion.

---

**License:** MIT | **Python:** 3.11+ | **Homepage:** [shotgun.sh](https://shotgun.sh/)
