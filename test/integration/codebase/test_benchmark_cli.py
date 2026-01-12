"""Integration tests for benchmark CLI commands."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from shotgun.codebase.benchmarks import (
    BenchmarkRunner,
    MetricsDisplayOptions,
    MetricsExporter,
    get_formatter,
)
from shotgun.utils.file_system_utils import get_shotgun_home


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    """Create a small sample repository for testing."""
    repo_path = tmp_path / "sample_repo"
    repo_path.mkdir()

    # Create a simple Python file
    src_dir = repo_path / "src"
    src_dir.mkdir()

    (src_dir / "__init__.py").write_text("")

    (src_dir / "main.py").write_text('''
"""Main module."""


class Calculator:
    """A simple calculator."""

    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    def subtract(self, a: int, b: int) -> int:
        """Subtract two numbers."""
        return a - b


def greet(name: str) -> str:
    """Greet someone."""
    return f"Hello, {name}!"


def main() -> None:
    """Main function."""
    calc = Calculator()
    print(calc.add(1, 2))
    print(greet("World"))
''')

    (src_dir / "utils.py").write_text('''
"""Utility functions."""


def format_string(s: str) -> str:
    """Format a string."""
    return s.strip().lower()


def parse_int(s: str) -> int:
    """Parse an integer."""
    return int(s)
''')

    return repo_path


@pytest.fixture
def cleanup_db(sample_repo: Path) -> None:
    """Clean up database after test."""
    yield
    # Clean up any databases created during test
    storage_dir = get_shotgun_home() / "codebases"
    graph_id = hashlib.sha256(str(sample_repo.resolve()).encode()).hexdigest()[:12]

    graph_path = storage_dir / f"{graph_id}.kuzu"
    if graph_path.exists():
        if graph_path.is_dir():
            shutil.rmtree(graph_path)
        else:
            graph_path.unlink()

    wal_path = storage_dir / f"{graph_id}.kuzu.wal"
    if wal_path.exists():
        wal_path.unlink()


@pytest.mark.asyncio
async def test_benchmark_runner_basic(sample_repo: Path, cleanup_db: None) -> None:
    """Test basic benchmark runner execution."""
    runner = BenchmarkRunner(
        codebase_path=sample_repo,
        codebase_name="test_repo",
        iterations=1,
        warmup_iterations=0,
        parallel=False,  # Use sequential for faster tests
        collect_file_metrics=True,
        collect_worker_metrics=False,
    )

    results = await runner.run()

    # Check basic properties
    assert results.codebase_name == "test_repo"
    assert results.codebase_path == str(sample_repo.resolve())
    assert results.config.iterations == 1
    assert len(results.measured_runs) == 1

    # Check metrics
    assert results.avg_duration_seconds > 0
    metrics = results.get_last_metrics()
    assert metrics is not None
    assert metrics.total_files > 0
    assert metrics.total_nodes > 0


@pytest.mark.asyncio
async def test_benchmark_runner_multiple_iterations(
    sample_repo: Path, cleanup_db: None
) -> None:
    """Test benchmark runner with multiple iterations."""
    runner = BenchmarkRunner(
        codebase_path=sample_repo,
        codebase_name="test_repo",
        iterations=2,
        warmup_iterations=0,
        parallel=False,
        collect_file_metrics=False,
        collect_worker_metrics=False,
    )

    results = await runner.run()

    # Check iterations
    assert len(results.measured_runs) == 2
    assert results.avg_duration_seconds > 0
    assert results.min_duration_seconds <= results.avg_duration_seconds
    assert results.max_duration_seconds >= results.avg_duration_seconds


@pytest.mark.asyncio
async def test_benchmark_runner_with_warmup(
    sample_repo: Path, cleanup_db: None
) -> None:
    """Test benchmark runner with warmup iterations."""
    runner = BenchmarkRunner(
        codebase_path=sample_repo,
        codebase_name="test_repo",
        iterations=1,
        warmup_iterations=1,
        parallel=False,
        collect_file_metrics=False,
        collect_worker_metrics=False,
    )

    results = await runner.run()

    # Check warmup and measured runs
    assert len(results.warmup_runs) == 1
    assert len(results.measured_runs) == 1


def test_json_formatter(sample_repo: Path) -> None:
    """Test JSON formatter produces valid JSON."""
    from shotgun.codebase.benchmarks.models import (
        BenchmarkConfig,
        BenchmarkMode,
        BenchmarkResults,
        BenchmarkRun,
    )
    from shotgun.codebase.core.metrics_types import IndexingMetrics

    config = BenchmarkConfig(mode=BenchmarkMode.SEQUENTIAL, iterations=1)
    results = BenchmarkResults(
        codebase_name="test",
        codebase_path=str(sample_repo),
        config=config,
    )

    metrics = IndexingMetrics(
        session_id="test",
        codebase_name="test",
        total_duration_seconds=5.0,
        phase_metrics={},
        file_metrics=[],
        total_files=50,
        total_nodes=200,
        total_relationships=400,
        avg_throughput=10.0,
        peak_memory_mb=100.0,
    )

    run = BenchmarkRun(run_id=0, is_warmup=False, metrics=metrics)
    results.add_run(run)
    results.calculate_statistics()

    formatter = get_formatter("json")
    options = MetricsDisplayOptions()
    output = formatter.format_results(results, options)

    # Should be valid JSON
    data = json.loads(output)
    assert data["codebase_name"] == "test"
    assert "statistics" in data
    assert "runs" in data


def test_markdown_formatter(sample_repo: Path) -> None:
    """Test Markdown formatter produces valid markdown."""
    from shotgun.codebase.benchmarks.models import (
        BenchmarkConfig,
        BenchmarkMode,
        BenchmarkResults,
        BenchmarkRun,
    )
    from shotgun.codebase.core.metrics_types import IndexingMetrics

    config = BenchmarkConfig(mode=BenchmarkMode.PARALLEL, worker_count=4, iterations=1)
    results = BenchmarkResults(
        codebase_name="test",
        codebase_path=str(sample_repo),
        config=config,
    )

    metrics = IndexingMetrics(
        session_id="test",
        codebase_name="test",
        total_duration_seconds=5.0,
        phase_metrics={},
        file_metrics=[],
        total_files=50,
        total_nodes=200,
        total_relationships=400,
        avg_throughput=10.0,
        peak_memory_mb=100.0,
    )

    run = BenchmarkRun(run_id=0, is_warmup=False, metrics=metrics)
    results.add_run(run)
    results.calculate_statistics()

    formatter = get_formatter("markdown")
    options = MetricsDisplayOptions()
    output = formatter.format_results(results, options)

    # Should contain markdown elements
    assert "#" in output  # Headers
    assert "|" in output  # Table
    assert "test" in output


def test_metrics_exporter_json(sample_repo: Path, tmp_path: Path) -> None:
    """Test MetricsExporter exports to JSON."""
    from shotgun.codebase.benchmarks.models import (
        BenchmarkConfig,
        BenchmarkMode,
        BenchmarkResults,
        BenchmarkRun,
    )
    from shotgun.codebase.core.metrics_types import IndexingMetrics

    config = BenchmarkConfig(mode=BenchmarkMode.SEQUENTIAL, iterations=1)
    results = BenchmarkResults(
        codebase_name="test",
        codebase_path=str(sample_repo),
        config=config,
    )

    metrics = IndexingMetrics(
        session_id="test",
        codebase_name="test",
        total_duration_seconds=5.0,
        phase_metrics={},
        file_metrics=[],
        total_files=50,
        total_nodes=200,
        total_relationships=400,
        avg_throughput=10.0,
        peak_memory_mb=100.0,
    )

    run = BenchmarkRun(run_id=0, is_warmup=False, metrics=metrics)
    results.add_run(run)
    results.calculate_statistics()

    # Export
    export_path = tmp_path / "metrics.json"
    exporter = MetricsExporter()
    exporter.export(results, export_path)

    # Verify file exists and is valid JSON
    assert export_path.exists()
    data = json.loads(export_path.read_text())
    assert data["codebase_name"] == "test"


def test_get_formatter_invalid_format() -> None:
    """Test get_formatter raises for invalid format."""
    with pytest.raises(ValueError, match="Unknown output format"):
        get_formatter("invalid_format")
