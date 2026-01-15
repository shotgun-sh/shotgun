"""Configuration and fixtures for performance tests.

Provides fixtures for generating medium-sized synthetic codebases
and measuring performance metrics.
"""

import gc
import hashlib
import random
import shutil
import threading
import time
from pathlib import Path

import psutil
import pytest

from shotgun.utils.file_system_utils import get_shotgun_home


def pytest_configure(config):
    """Configure pytest for performance tests."""
    config.addinivalue_line(
        "markers",
        "performance: mark test as performance benchmark (deselect with '-m \"not performance\"')",
    )


@pytest.fixture(scope="module")
def medium_python_codebase(tmp_path_factory) -> Path:
    """Generate a medium-sized Python codebase for benchmarking.

    Generates ~2000 Python files across 50 packages.
    Each module contains classes, functions, and method calls.

    This fixture is module-scoped to avoid regenerating for each test.
    """
    base_tmp = tmp_path_factory.mktemp("benchmark_codebase")
    codebase_dir = base_tmp / "generated_codebase"
    codebase_dir.mkdir(parents=True, exist_ok=True)

    # Configuration for codebase generation
    package_count = 50
    modules_per_package = 40  # ~2000 files total

    all_function_names: list[str] = []
    random.seed(42)  # Reproducible generation

    for pkg_idx in range(package_count):
        pkg_name = f"package_{pkg_idx:03d}"
        pkg_dir = codebase_dir / pkg_name
        pkg_dir.mkdir(parents=True, exist_ok=True)

        # Create __init__.py
        (pkg_dir / "__init__.py").write_text(f'"""Package {pkg_name}."""\n')

        for mod_idx in range(modules_per_package):
            mod_name = f"module_{mod_idx:03d}"
            content = _generate_module_content(
                pkg_name, mod_name, mod_idx, all_function_names
            )
            (pkg_dir / f"{mod_name}.py").write_text(content)

    return codebase_dir


def _generate_module_content(
    pkg_name: str,
    mod_name: str,
    mod_idx: int,
    all_function_names: list[str],
) -> str:
    """Generate content for a single Python module.

    Creates realistic Python code with classes, methods, and functions.
    """
    lines = [f'"""Module {pkg_name}.{mod_name}."""', ""]

    # Add imports
    import_count = random.randint(1, 3)  # noqa: S311
    imports = [
        "from typing import Any, Optional",
        "from pathlib import Path",
        "import os",
    ]
    lines.extend(imports[:import_count])
    lines.append("")

    # Generate classes (0-3 per module)
    class_count = random.randint(0, 3)  # noqa: S311
    for cls_idx in range(class_count):
        class_name = f"Class{mod_name.title().replace('_', '')}{cls_idx}"
        lines.append(_generate_class(class_name, all_function_names))

    # Generate standalone functions (2-10 per module)
    func_count = random.randint(2, 10)  # noqa: S311
    for func_idx in range(func_count):
        func_name = f"function_{mod_idx}_{func_idx}"
        all_function_names.append(f"{pkg_name}.{mod_name}.{func_name}")
        lines.append(_generate_function(func_name))

    return "\n".join(lines)


def _generate_class(class_name: str, all_function_names: list[str]) -> str:
    """Generate a Python class with methods."""
    method_count = random.randint(1, 5)  # noqa: S311
    methods = []

    for meth_idx in range(method_count):
        method_name = f"method_{meth_idx}"
        all_function_names.append(f"{class_name}.{method_name}")

        # Generate method body
        body_lines = ["        result = self.value"]
        if random.random() > 0.7:  # noqa: S311
            body_lines.append("        self._helper()")
        body_lines.append("        return result")

        methods.append(
            f"""
    def {method_name}(self) -> int:
        \"\"\"Method {method_name}.\"\"\"
{chr(10).join(body_lines)}"""
        )

    return f'''
class {class_name}:
    """Generated class {class_name}."""

    def __init__(self, value: int = 0):
        """Initialize with value."""
        self.value = value

    def _helper(self) -> None:
        \"\"\"Private helper method.\"\"\"
        pass
{"".join(methods)}
'''


def _generate_function(func_name: str) -> str:
    """Generate a standalone Python function."""
    return f'''
def {func_name}(x: int, y: int = 0) -> int:
    """Generated function {func_name}."""
    return x + y
'''


def cleanup_database_for_path(codebase_path: Path) -> None:
    """Clean up database files for a given codebase path.

    This is a shared utility that can be used both by fixtures and
    within tests (e.g., between benchmark runs).
    """
    storage_dir = get_shotgun_home() / "codebases"
    graph_id = hashlib.sha256(str(codebase_path.resolve()).encode()).hexdigest()[:12]

    graph_path = storage_dir / f"{graph_id}.kuzu"
    if graph_path.exists():
        if graph_path.is_dir():
            shutil.rmtree(graph_path, ignore_errors=True)
        else:
            graph_path.unlink(missing_ok=True)

    wal_path = storage_dir / f"{graph_id}.kuzu.wal"
    if wal_path.exists():
        wal_path.unlink(missing_ok=True)

    # Force garbage collection
    gc.collect()


@pytest.fixture
def cleanup_benchmark_db(medium_python_codebase: Path):
    """Clean up database files after benchmark tests."""
    yield
    cleanup_database_for_path(medium_python_codebase)


class CPUSampler:
    """Background thread for sampling CPU utilization."""

    def __init__(self, interval: float = 0.1):
        """Initialize CPU sampler.

        Args:
            interval: Sampling interval in seconds
        """
        self.interval = interval
        self.samples: list[float] = []
        self._running = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start sampling CPU utilization."""
        self._running.set()
        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()

    def stop(self) -> list[float]:
        """Stop sampling and return collected samples."""
        self._running.clear()
        if self._thread:
            self._thread.join(timeout=1.0)
        return self.samples

    def _sample_loop(self) -> None:
        """Background loop for CPU sampling."""
        while self._running.is_set():
            self.samples.append(psutil.cpu_percent(interval=self.interval))

    def get_average(self, trim_percent: float = 0.1) -> float:
        """Get average CPU utilization, optionally trimming outliers.

        Args:
            trim_percent: Percentage of samples to trim from start/end

        Returns:
            Average CPU utilization percentage
        """
        if not self.samples:
            return 0.0

        if len(self.samples) > 10:
            trim_count = int(len(self.samples) * trim_percent)
            trimmed = (
                self.samples[trim_count:-trim_count] if trim_count > 0 else self.samples
            )
        else:
            trimmed = self.samples

        return sum(trimmed) / len(trimmed) if trimmed else 0.0


class MemorySampler:
    """Background thread for sampling memory usage."""

    def __init__(self, interval: float = 0.1):
        """Initialize memory sampler.

        Args:
            interval: Sampling interval in seconds
        """
        self.interval = interval
        self.samples: list[float] = []
        self._process = psutil.Process()
        self._running = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start sampling memory usage."""
        self._running.set()
        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()

    def stop(self) -> list[float]:
        """Stop sampling and return collected samples."""
        self._running.clear()
        if self._thread:
            self._thread.join(timeout=1.0)
        return self.samples

    def _sample_loop(self) -> None:
        """Background loop for memory sampling."""
        while self._running.is_set():
            memory_mb = self._process.memory_info().rss / (1024 * 1024)
            self.samples.append(memory_mb)
            time.sleep(self.interval)

    def get_peak(self) -> float:
        """Get peak memory usage in MB."""
        return max(self.samples) if self.samples else 0.0


@pytest.fixture
def cpu_sampler() -> CPUSampler:
    """Create a CPU sampler for tests."""
    return CPUSampler(interval=0.1)


@pytest.fixture
def memory_sampler() -> MemorySampler:
    """Create a memory sampler for tests."""
    return MemorySampler(interval=0.1)
