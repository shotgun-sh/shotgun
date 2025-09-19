"""Hatchling build hook for generating build constants."""

import os
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import (
    BuildHookInterface,  # type: ignore[import-not-found]
)


class CustomBuildHook(BuildHookInterface):  # type: ignore[misc]
    """Custom build hook to generate build constants from environment variables."""

    def initialize(self, version, build_data):  # type: ignore[no-untyped-def]
        """Generate build constants file from environment variables.

        This runs immediately before each build.
        """
        # Only generate constants if SENTRY_DSN is provided (production builds)
        sentry_dsn = os.environ.get("SENTRY_DSN", "")

        # Get PostHog configuration from environment
        posthog_api_key = os.environ.get("POSTHOG_API_KEY", "")
        posthog_project_id = os.environ.get("POSTHOG_PROJECT_ID", "")

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

# Build metadata
BUILD_TIME_ENV = "production" if SENTRY_DSN else "development"
'''

        # Write to build_constants.py in the source directory
        output_path = Path(self.root) / "src" / "shotgun" / "build_constants.py"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(constants_content)

        # Log the build hook execution
        if sentry_dsn or posthog_api_key:
            features = []
            if sentry_dsn:
                features.append("Sentry")
            if posthog_api_key:
                features.append("PostHog")
            print(
                f"✅ Generated build_constants.py with {', '.join(features)} (production build)"
            )
        else:
            print(
                "⚠️  Generated build_constants.py without analytics keys (development build)"
            )
