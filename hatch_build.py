"""Hatchling build hook for generating build constants."""

import os
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from packaging.version import InvalidVersion, Version


def _require_validation() -> bool:
    """Check if build validation is explicitly required.

    Validation is skipped by default (for local dev and CI test jobs).
    Set SHOTGUN_BUILD_REQUIRE_VALIDATION=true in production builds to enforce.
    """
    return os.environ.get("SHOTGUN_BUILD_REQUIRE_VALIDATION", "").lower() in (
        "1",
        "true",
        "yes",
    )


class CustomBuildHook(BuildHookInterface):  # type: ignore[type-arg]
    """Custom build hook to generate build constants from environment variables."""

    def initialize(self, version, build_data):  # type: ignore[no-untyped-def]
        """Generate build constants file from environment variables.

        This runs immediately before each build.
        """
        # Get actual package version from metadata (not the 'version' param which is build target)
        # The 'version' parameter is the build target ('standard', 'editable', etc.), NOT the package version
        package_version = self.metadata.core.version

        # First validate it's a valid PEP 440 version (catches things like "abc.def.ghi")
        try:
            Version(str(package_version))
        except InvalidVersion as e:
            raise ValueError(
                f"❌ Invalid version format: {package_version!r}\n"
                f"   Must be a valid PEP 440 version string\n"
                f"   Error: {e}"
            ) from e

        # Then enforce strict X.Y.Z format (packaging.version accepts "1.0" but we require "1.0.0")
        version_parts = str(package_version).split(".")
        if len(version_parts) < 3 or not all(
            part.split("dev")[0].split("rc")[0].split("a")[0].split("b")[0].isdigit()
            for part in version_parts[:3]
        ):
            raise ValueError(
                f"❌ Invalid version format: {package_version!r}\n"
                f"   Must start with X.Y.Z where X, Y, Z are numbers (e.g., 0.2.22, 1.0.0)\n"
                f"   Valid: 0.2.22, 1.0.0, 0.2.22.dev1\n"
                f"   Invalid: 1.0, 2022.1, abc.def.ghi"
            )

        # Check if this is a development build based on package version
        is_dev_build = any(
            marker in str(package_version)
            for marker in ["dev", "rc", "alpha", "beta", "a", "b"]
        )

        # Validation is skipped by default (for local dev and CI test jobs)
        # Set SHOTGUN_BUILD_REQUIRE_VALIDATION=true in production builds to enforce
        skip_validation = not _require_validation()

        if skip_validation:
            print("ℹ️  Build validation skipped (default behavior)")
        else:
            print(
                "ℹ️  Build validation required (SHOTGUN_BUILD_REQUIRE_VALIDATION=true)"
            )

        # Get Sentry configuration from environment (SHOTGUN_ prefix for production builds)
        sentry_dsn = os.environ.get("SHOTGUN_SENTRY_DSN", "")

        # Validate that Sentry DSN is present for all builds (unless skipped)
        if not skip_validation and not sentry_dsn:
            raise ValueError(
                "❌ SHOTGUN_SENTRY_DSN is required for builds but not found in environment. "
                "Ensure the GitHub secret SENTRY_DSN is set and passed to the build."
            )

        # Get PostHog configuration from environment (SHOTGUN_ prefix)
        posthog_api_key = os.environ.get("SHOTGUN_POSTHOG_API_KEY", "")
        posthog_project_id = os.environ.get("SHOTGUN_POSTHOG_PROJECT_ID", "")

        # Validate that PostHog keys are present for all builds (unless skipped)
        # This ensures we never deploy without analytics configured
        if not skip_validation:
            if not posthog_api_key:
                raise ValueError(
                    "❌ SHOTGUN_POSTHOG_API_KEY is required for builds but not found in environment. "
                    "Ensure the GitHub secret POSTHOG_API_KEY is set and passed to the build."
                )
            if not posthog_project_id:
                raise ValueError(
                    "❌ SHOTGUN_POSTHOG_PROJECT_ID is required for builds but not found in environment. "
                    "Ensure the GitHub secret POSTHOG_PROJECT_ID is set and passed to the build."
                )

        # Get Logfire configuration (SHOTGUN_ prefix, only for dev builds)
        logfire_enabled = ""
        logfire_token = ""
        if is_dev_build:
            logfire_enabled = os.environ.get("SHOTGUN_LOGFIRE_ENABLED", "")
            logfire_token = os.environ.get("SHOTGUN_LOGFIRE_TOKEN", "")

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
                f"✅ Generated build_constants.py for v{package_version} with {', '.join(features)} ({build_type} build)"
            )
        else:
            print(
                f"⚠️  Generated build_constants.py for v{package_version} without analytics keys (development build)"
            )
