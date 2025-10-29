# Docker Guide

Run Shotgun in a Docker container with web access for easy deployment and isolated environments.

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

### What This Does

- Maps port 8000 from the container to your host
- Mounts your current directory as `/workspace` inside the container
- Mounts your Shotgun config directory to persist API keys and settings
- Automatically prompts you to index the codebase on startup

## Available Images

### Using Pre-built Images (Recommended)

Pull the official image from GitHub Container Registry:

```bash
# Pull latest stable version
docker pull ghcr.io/shotgun-sh/shotgun:latest

# Or pull a specific version
docker pull ghcr.io/shotgun-sh/shotgun:v0.1.0

# Or pull development version (not recommended)
docker pull ghcr.io/shotgun-sh/shotgun:dev
```

### Available Tags

- **`latest`** - ✅ **Recommended** - Latest stable release (secure, minimal telemetry)
- **`v0.1.0`** - Specific version tags (for pinning to a particular version)
- **`dev`** - ❌ **Not recommended** - Development version with full telemetry (for developers only)

### ⚠️ Important: Use the Stable Release

**Always use the `latest` tag for production use.**

**DO NOT use the `:dev` tag unless you are a developer testing new features.**

Development versions (`:dev`):
- ❌ Have telemetry and logging built-in that you probably don't want
- ❌ Never auto-update (you'll be stuck on that version)
- ❌ Are for internal testing only

Production versions (`:latest` and version tags like `:v0.1.0`) are secure and only log anonymous event metadata - no user data is collected.

## Building from Source (Optional)

If you prefer to build the image yourself:

```bash
docker build -t shotgun:latest .
```

## Running the Container

### Volume Mounts

The container requires two volume mounts:

1. **Workspace directory** - Your codebase (mounted to `/workspace`)
2. **Config directory** - API keys and settings (mounted to `/home/shotgun/.shotgun-sh`)

### Basic Usage

```bash
# Basic usage (serves on port 8000)
docker run -p 8000:8000 \
  -v $(pwd):/workspace \
  -v ~/.shotgun-sh:/home/shotgun/.shotgun-sh \
  ghcr.io/shotgun-sh/shotgun:latest
```

### Custom Port

To use a different port:

```bash
docker run -p 3000:3000 \
  -v $(pwd):/workspace \
  -v ~/.shotgun-sh:/home/shotgun/.shotgun-sh \
  ghcr.io/shotgun-sh/shotgun:latest --port 3000
```

### Different Codebase Directory

```bash
docker run -p 8000:8000 \
  -v /path/to/your/project:/workspace \
  -v ~/.shotgun-sh:/home/shotgun/.shotgun-sh \
  ghcr.io/shotgun-sh/shotgun:latest
```

### Background Mode with Auto-Restart

Run in the background with automatic restart on failure:

```bash
docker run -d --restart unless-stopped \
  --name shotgun-web \
  -p 8000:8000 \
  -v $(pwd):/workspace \
  -v ~/.shotgun-sh:/home/shotgun/.shotgun-sh \
  ghcr.io/shotgun-sh/shotgun:latest
```

Manage the background container:

```bash
# View logs
docker logs shotgun-web

# Follow logs
docker logs -f shotgun-web

# Stop the container
docker stop shotgun-web

# Start the container
docker start shotgun-web

# Remove the container
docker rm shotgun-web
```

## Configuration

### Initial Setup

On first run, configure your API keys through the web UI at http://localhost:8000. The configuration will persist in the mounted `~/.shotgun-sh` directory.

### Codebase Indexing

The Docker image automatically prompts you to index the codebase on each startup. This ensures you're always working with up-to-date code analysis, even if the container restarts or you mount a different directory. Simply click "Index now" when prompted.

**Note:** The Docker image automatically includes `--force-reindex` to ensure fresh indexing on startup. You don't need to add any additional flags.

### Persistent Configuration

Because we mount `~/.shotgun-sh` from your host:
- API keys are saved between container restarts
- User preferences persist
- Configuration is shared with local Shotgun installations
- No need to reconfigure on each run

## Advanced Usage

### Environment Variables

Pass environment variables to the container:

```bash
docker run -p 8000:8000 \
  -v $(pwd):/workspace \
  -v ~/.shotgun-sh:/home/shotgun/.shotgun-sh \
  -e SHOTGUN_LOGFIRE_ENABLED=true \
  -e SHOTGUN_LOGFIRE_TOKEN=your-token \
  ghcr.io/shotgun-sh/shotgun:latest
```

### Custom Command-Line Arguments

The container accepts any Shotgun CLI arguments:

```bash
docker run -p 8000:8000 \
  -v $(pwd):/workspace \
  -v ~/.shotgun-sh:/home/shotgun/.shotgun-sh \
  ghcr.io/shotgun-sh/shotgun:latest --no-update-check --port 3000
```

### Docker Compose

Create a `docker-compose.yml` file:

```yaml
version: '3.8'

services:
  shotgun:
    image: ghcr.io/shotgun-sh/shotgun:latest
    ports:
      - "8000:8000"
    volumes:
      - ./:/workspace
      - ~/.shotgun-sh:/home/shotgun/.shotgun-sh
    restart: unless-stopped
    container_name: shotgun-web
```

Run with:

```bash
docker-compose up -d
```

### Multiple Projects

Run separate containers for different projects:

```bash
# Project 1
docker run -d --name shotgun-project1 \
  -p 8001:8000 \
  -v /path/to/project1:/workspace \
  -v ~/.shotgun-sh:/home/shotgun/.shotgun-sh \
  ghcr.io/shotgun-sh/shotgun:latest

# Project 2
docker run -d --name shotgun-project2 \
  -p 8002:8000 \
  -v /path/to/project2:/workspace \
  -v ~/.shotgun-sh:/home/shotgun/.shotgun-sh \
  ghcr.io/shotgun-sh/shotgun:latest
```

Access at:
- Project 1: http://localhost:8001
- Project 2: http://localhost:8002

## Troubleshooting

### Permission Issues

If you encounter permission issues with mounted volumes:

```bash
# Option 1: Run as your user
docker run --user $(id -u):$(id -g) \
  -p 8000:8000 \
  -v $(pwd):/workspace \
  -v ~/.shotgun-sh:/home/shotgun/.shotgun-sh \
  ghcr.io/shotgun-sh/shotgun:latest

# Option 2: Fix permissions on host
chmod -R 755 ~/.shotgun-sh
```

### Port Already in Use

If port 8000 is already in use:

```bash
# Check what's using the port
lsof -i :8000

# Use a different port
docker run -p 8080:8000 \
  -v $(pwd):/workspace \
  -v ~/.shotgun-sh:/home/shotgun/.shotgun-sh \
  ghcr.io/shotgun-sh/shotgun:latest
```

### Container Won't Start

Check logs for errors:

```bash
docker logs shotgun-web
```

Common issues:
- Invalid volume paths
- Missing config directory
- Port conflicts
- Insufficient permissions

### Codebase Not Indexing

If the codebase doesn't index properly:

1. Ensure workspace is mounted correctly: `docker exec shotgun-web ls /workspace`
2. Check you're in the right directory on host
3. Verify directory permissions
4. Try rebuilding the index through web UI

### Slow Performance

If the container is slow:

- Increase Docker resource limits (CPU/Memory)
- Use faster storage for Docker volumes
- Consider using local installation for better performance
- Check if antivirus is scanning Docker volumes

## Security Considerations

### Network Exposure

By default, the container binds to `0.0.0.0:8000`, making it accessible from any network interface. For security:

```bash
# Bind only to localhost
docker run -p 127.0.0.1:8000:8000 \
  -v $(pwd):/workspace \
  -v ~/.shotgun-sh:/home/shotgun/.shotgun-sh \
  ghcr.io/shotgun-sh/shotgun:latest
```

### API Keys

- API keys are stored in mounted `~/.shotgun-sh` directory
- Never commit this directory to version control
- Use environment variables for CI/CD scenarios
- Rotate keys if container is compromised

### Production Deployment

For production deployments:

- Use specific version tags, not `:latest`
- Set up proper authentication/authorization
- Use HTTPS with reverse proxy (nginx, traefik)
- Implement rate limiting
- Monitor container logs
- Keep images updated

## Performance Tips

### Resource Limits

Set resource limits for production:

```bash
docker run -d \
  --memory="2g" \
  --cpus="2.0" \
  -p 8000:8000 \
  -v $(pwd):/workspace \
  -v ~/.shotgun-sh:/home/shotgun/.shotgun-sh \
  ghcr.io/shotgun-sh/shotgun:latest
```

### Volume Performance

For better I/O performance on macOS/Windows:

```bash
# Use delegated volume mounts (macOS)
docker run -p 8000:8000 \
  -v $(pwd):/workspace:delegated \
  -v ~/.shotgun-sh:/home/shotgun/.shotgun-sh:delegated \
  ghcr.io/shotgun-sh/shotgun:latest
```

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [GitHub Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Shotgun Main Documentation](../README.md)

## Support

- Join our [Discord community](https://discord.gg/5RmY6J2N7s)
- Report issues on [GitHub](https://github.com/shotgun-sh/shotgun/issues)
- Check the [FAQ](../README.md#faq)
