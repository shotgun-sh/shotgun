"""Shared specs file utilities.

This module provides utilities for scanning and hashing files in the
.shotgun/ directory for upload to the shared specs API.
"""

from shotgun.shotgun_web.shared_specs.file_scanner import (
    get_shotgun_directory,
    scan_shotgun_directory,
)
from shotgun.shotgun_web.shared_specs.hasher import (
    calculate_sha256,
    calculate_sha256_with_size,
)
from shotgun.shotgun_web.shared_specs.models import (
    UploadProgress,
    UploadResult,
)
from shotgun.shotgun_web.shared_specs.upload_pipeline import run_upload_pipeline
from shotgun.shotgun_web.shared_specs.utils import UploadPhase, format_bytes

__all__ = [
    "UploadPhase",
    "UploadProgress",
    "UploadResult",
    "calculate_sha256",
    "calculate_sha256_with_size",
    "format_bytes",
    "get_shotgun_directory",
    "run_upload_pipeline",
    "scan_shotgun_directory",
]
