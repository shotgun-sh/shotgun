# Use Python 3.13 slim as base image
FROM python:3.13-slim

# Build arguments for telemetry configuration
# These are used during the build process to embed analytics keys
ARG SHOTGUN_POSTHOG_API_KEY=""
ARG SHOTGUN_POSTHOG_PROJECT_ID=""
ARG SHOTGUN_BUILD_REQUIRE_VALIDATION=""

# OCI annotations for package metadata
LABEL org.opencontainers.image.title="Shotgun" \
      org.opencontainers.image.description="AI-powered CLI tool for research, planning, and task management. Always use :latest for production - see README for details." \
      org.opencontainers.image.source="https://github.com/shotgun-sh/shotgun" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.vendor="Shotgun" \
      org.opencontainers.image.url="https://shotgun.sh"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1

# Install uv for dependency management
RUN pip install --no-cache-dir uv

# Create non-root user
RUN useradd -m -u 1000 shotgun

# Set working directory for build
WORKDIR /app

# Copy project files
COPY --chown=shotgun:shotgun pyproject.toml uv.lock hatch_build.py ./
COPY --chown=shotgun:shotgun src/ ./src/
COPY --chown=shotgun:shotgun README.md LICENSE ./
COPY --chown=shotgun:shotgun docs/README_DOCKER.md ./docs/

# Install dependencies
# Pass build args as environment variables for the build hook
RUN SHOTGUN_POSTHOG_API_KEY="${SHOTGUN_POSTHOG_API_KEY}" \
    SHOTGUN_POSTHOG_PROJECT_ID="${SHOTGUN_POSTHOG_PROJECT_ID}" \
    SHOTGUN_BUILD_REQUIRE_VALIDATION="${SHOTGUN_BUILD_REQUIRE_VALIDATION}" \
    uv sync --frozen --no-dev

# Create directories for workspace and config
RUN mkdir -p /workspace /home/shotgun/.shotgun-sh && \
    chown -R shotgun:shotgun /workspace /home/shotgun/.shotgun-sh

# Switch to non-root user
USER shotgun

# Set working directory to workspace
WORKDIR /workspace

# Expose default web server port
EXPOSE 8000

# Health check for web server
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000').read()" || exit 1

# Add .venv/bin to PATH so shotgun command is available
ENV PATH="/app/.venv/bin:$PATH"

# Entry point - run shotgun in web mode with force-reindex for Docker
ENTRYPOINT ["shotgun", "--web", "--host", "0.0.0.0", "--force-reindex"]

# Default port (can be overridden)
CMD ["--port", "8000"]
