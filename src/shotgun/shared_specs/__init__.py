"""Shared specs file utilities.

This module provides utilities for scanning and hashing files in the
.shotgun/ directory for upload to the shared specs API.
"""

from shotgun.shared_specs.file_scanner import (
    get_shotgun_directory,
    scan_shotgun_directory,
)
from shotgun.shared_specs.hasher import (
    calculate_sha256,
    calculate_sha256_with_size,
)
from shotgun.shared_specs.upload_pipeline import (
    UploadProgress,
    UploadResult,
    run_upload_pipeline,
)

__all__ = [
    "UploadProgress",
    "UploadResult",
    "calculate_sha256",
    "calculate_sha256_with_size",
    "get_shotgun_directory",
    "run_upload_pipeline",
    "scan_shotgun_directory",
]
