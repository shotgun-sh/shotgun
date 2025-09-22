"""Hatchling build hook for generating build constants."""

import os
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):  # type: ignore[type-arg]
    """Custom build hook to generate build constants from environment variables."""

    def initialize(self, version, build_data):  # type: ignore[no-untyped-def]
        """Generate build constants file from environment variables.

        This runs immediately before each build.
        """
        # Check if this is a development build based on version
        is_dev_build = any(
            marker in str(version)
            for marker in ["dev", "rc", "alpha", "beta", "a", "b"]
        )

        # Only generate constants if SENTRY_DSN is provided (production builds)
        sentry_dsn = os.environ.get("SENTRY_DSN", "")

        # Get PostHog configuration from environment
        posthog_api_key = os.environ.get("POSTHOG_API_KEY", "")
        posthog_project_id = os.environ.get("POSTHOG_PROJECT_ID", "")

        # Get Logfire configuration (only for dev builds)
        logfire_enabled = ""
        logfire_token = ""
        if is_dev_build:
            logfire_enabled = os.environ.get("LOGFIRE_ENABLED", "")
            logfire_token = os.environ.get("LOGFIRE_TOKEN", "")

        # Generate Python configuration file with build-time constants
        constants_content = f'''"""Build-time constants generated during packaging.

This file is auto-generated during the build process.
DO NOT EDIT MANUALLY.
"""

# Sentry DSN embedded at build time (empty string if not provided)
SENTRY_DSN = {repr(sentry_dsn)}

# PostHog configuration embedded at build time (empty strings if not provided)
POSTHOG_API_KEY = {repr(posthog_api_key)}
POSTHOG_PROJECT_ID = {repr(posthog_project_id)}

# Logfire configuration embedded at build time (only for dev builds)
LOGFIRE_ENABLED = {repr(logfire_enabled)}
LOGFIRE_TOKEN = {repr(logfire_token)}

# Build metadata
BUILD_TIME_ENV = "production" if SENTRY_DSN else "development"
IS_DEV_BUILD = {repr(is_dev_build)}
'''

        # Write to build_constants.py in the source directory
        output_path = Path(self.root) / "src" / "shotgun" / "build_constants.py"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(constants_content)

        # Log the build hook execution
        features = []
        if sentry_dsn:
            features.append("Sentry")
        if posthog_api_key:
            features.append("PostHog")
        if logfire_enabled and logfire_token:
            features.append("Logfire")

        if features:
            build_type = "development" if is_dev_build else "production"
            print(
                f"✅ Generated build_constants.py with {', '.join(features)} ({build_type} build)"
            )
        else:
            print(
                "⚠️  Generated build_constants.py without analytics keys (development build)"
            )
