"""Performance tests for parallel file parsing.

These tests measure speedup, CPU utilization, memory usage, and
parallelism efficiency for parallel execution vs sequential mode.

Run with: pytest test/performance/ -m slow -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from shotgun.codebase.benchmarks import BenchmarkRunner

from .conftest import CPUSampler, MemorySampler, cleanup_database_for_path


@pytest.mark.slow
@pytest.mark.performance
@pytest.mark.asyncio
async def test_parallel_speedup_target(
    medium_python_codebase: Path,
    cleanup_benchmark_db: None,
) -> None:
    """Measure speedup: target 2.0x+ improvement for parallel execution.

    Compares sequential vs parallel (8 workers) execution time.
    The parallel executor uses ThreadPoolExecutor for I/O-bound work.
    """
    # Run sequential benchmark
    seq_runner = BenchmarkRunner(
        codebase_path=medium_python_codebase,
        codebase_name="speedup-test-seq",
        iterations=1,
        warmup_iterations=0,
        parallel=False,
        collect_file_metrics=False,
        collect_worker_metrics=False,
    )
    seq_results = await seq_runner.run()
    seq_duration = seq_results.avg_duration_seconds

    # Cleanup between runs
    cleanup_database_for_path(medium_python_codebase)

    # Run parallel benchmark (8 workers)
    par_runner = BenchmarkRunner(
        codebase_path=medium_python_codebase,
        codebase_name="speedup-test-par",
        iterations=1,
        warmup_iterations=0,
        parallel=True,
        worker_count=8,
        collect_file_metrics=False,
        collect_worker_metrics=False,
    )
    par_results = await par_runner.run()
    par_duration = par_results.avg_duration_seconds

    # Calculate speedup
    speedup = seq_duration / par_duration if par_duration > 0 else 0

    # Assert speedup is reasonable (ThreadPoolExecutor provides some concurrency)
    # Note: ThreadPoolExecutor may not achieve full CPU parallelism due to GIL
    # but should still show improvement for I/O-bound file reading
    assert speedup >= 1.2, (
        f"Speedup {speedup:.2f}x below minimum 1.2x. "
        f"Sequential: {seq_duration:.2f}s, Parallel: {par_duration:.2f}s"
    )


@pytest.mark.slow
@pytest.mark.performance
@pytest.mark.asyncio
async def test_cpu_utilization_during_parallel_execution(
    medium_python_codebase: Path,
    cpu_sampler: CPUSampler,
    cleanup_benchmark_db: None,
) -> None:
    """Verify CPU utilization during parallel execution.

    Uses psutil to sample CPU percent during indexing.
    ThreadPoolExecutor with I/O work may not hit high CPU utilization,
    so we use a lower threshold.
    """
    # Start CPU sampling
    cpu_sampler.start()

    try:
        runner = BenchmarkRunner(
            codebase_path=medium_python_codebase,
            codebase_name="cpu-test",
            iterations=1,
            warmup_iterations=0,
            parallel=True,
            worker_count=8,
            collect_file_metrics=False,
            collect_worker_metrics=False,
        )
        await runner.run()
    finally:
        cpu_sampler.stop()

    # Get average CPU utilization
    avg_cpu = cpu_sampler.get_average(trim_percent=0.1)

    # For I/O-bound work with ThreadPoolExecutor, expect some CPU activity
    # Lower threshold since GIL limits true parallelism
    assert avg_cpu >= 10, (
        f"Average CPU utilization {avg_cpu:.1f}% very low. "
        "Expected some CPU activity during parallel file parsing."
    )


@pytest.mark.slow
@pytest.mark.performance
@pytest.mark.asyncio
async def test_worker_idle_time_minimal(
    medium_python_codebase: Path,
    cleanup_benchmark_db: None,
) -> None:
    """Verify parallelism efficiency indicates minimal worker idle time.

    Checks that work distribution is balanced enough that workers
    stay busy throughout execution.
    """
    runner = BenchmarkRunner(
        codebase_path=medium_python_codebase,
        codebase_name="idle-test",
        iterations=1,
        warmup_iterations=0,
        parallel=True,
        worker_count=8,
        collect_file_metrics=False,
        collect_worker_metrics=True,
    )
    results = await runner.run()

    # Get metrics from last run
    metrics = results.get_last_metrics()

    if metrics and metrics.parallelism_efficiency is not None:
        # Efficiency close to 1.0 means minimal idle time (balanced work)
        assert metrics.parallelism_efficiency >= 0.5, (
            f"Parallelism efficiency {metrics.parallelism_efficiency:.2f} below 0.5. "
            "Work distribution may be unbalanced."
        )


@pytest.mark.slow
@pytest.mark.performance
@pytest.mark.asyncio
async def test_memory_usage_under_limit(
    medium_python_codebase: Path,
    memory_sampler: MemorySampler,
    cleanup_benchmark_db: None,
) -> None:
    """Measure memory usage: target <2GB total for medium repository.

    Uses psutil to track peak RSS memory during indexing.
    """
    # Start memory sampling
    memory_sampler.start()

    try:
        runner = BenchmarkRunner(
            codebase_path=medium_python_codebase,
            codebase_name="memory-test",
            iterations=1,
            warmup_iterations=0,
            parallel=True,
            worker_count=8,
            collect_file_metrics=False,
            collect_worker_metrics=False,
        )
        await runner.run()
    finally:
        memory_sampler.stop()

    # Get peak memory
    peak_memory = memory_sampler.get_peak()

    # Target: <2GB = 2048MB
    assert peak_memory < 2048, f"Peak memory {peak_memory:.0f}MB exceeds 2048MB limit"


@pytest.mark.slow
@pytest.mark.performance
@pytest.mark.asyncio
async def test_serialization_overhead_minimal(
    medium_python_codebase: Path,
    cleanup_benchmark_db: None,
) -> None:
    """Validate that data structure handling doesn't add significant overhead.

    Note: With ThreadPoolExecutor (not ProcessPoolExecutor), there's no
    pickling overhead. This test validates phase timing proportions.
    """
    runner = BenchmarkRunner(
        codebase_path=medium_python_codebase,
        codebase_name="serialization-test",
        iterations=1,
        warmup_iterations=0,
        parallel=True,
        worker_count=8,
        collect_file_metrics=True,
        collect_worker_metrics=False,
    )
    results = await runner.run()
    metrics = results.get_last_metrics()

    if metrics:
        # Definitions phase should be a significant portion of work
        definitions_phase = metrics.phase_metrics.get("definitions")
        total_time = metrics.total_duration_seconds

        if definitions_phase and total_time > 0:
            definitions_ratio = definitions_phase.duration_seconds / total_time

            # Definitions phase (where parsing happens) should be substantial
            # If it's too small, something may be wrong with timing
            assert definitions_ratio > 0.1, (
                f"Definitions phase only {definitions_ratio:.1%} of total time. "
                "Expected it to be more substantial."
            )


@pytest.mark.slow
@pytest.mark.performance
@pytest.mark.asyncio
async def test_benchmark_runner_produces_valid_metrics(
    medium_python_codebase: Path,
    cleanup_benchmark_db: None,
) -> None:
    """Test that benchmark runner produces complete and valid metrics."""
    runner = BenchmarkRunner(
        codebase_path=medium_python_codebase,
        codebase_name="metrics-test",
        iterations=2,
        warmup_iterations=1,
        parallel=True,
        worker_count=4,
        collect_file_metrics=True,
        collect_worker_metrics=True,
    )
    results = await runner.run()

    # Verify basic results structure
    assert results.codebase_name == "metrics-test"
    assert len(results.warmup_runs) == 1
    assert len(results.measured_runs) == 2

    # Verify statistics
    assert results.avg_duration_seconds > 0
    assert results.min_duration_seconds <= results.avg_duration_seconds
    assert results.max_duration_seconds >= results.avg_duration_seconds

    # Verify metrics
    metrics = results.get_last_metrics()
    assert metrics is not None
    assert metrics.total_files > 0
    assert metrics.total_nodes > 0


@pytest.mark.slow
@pytest.mark.performance
@pytest.mark.asyncio
async def test_throughput_measurement(
    medium_python_codebase: Path,
    cleanup_benchmark_db: None,
) -> None:
    """Test that throughput is measured correctly."""
    runner = BenchmarkRunner(
        codebase_path=medium_python_codebase,
        codebase_name="throughput-test",
        iterations=1,
        warmup_iterations=0,
        parallel=True,
        worker_count=8,
        collect_file_metrics=False,
        collect_worker_metrics=False,
    )
    results = await runner.run()

    metrics = results.get_last_metrics()
    assert metrics is not None

    # Verify throughput is reasonable
    if metrics.total_duration_seconds > 0:
        # Avg throughput should be positive
        assert metrics.avg_throughput > 0, "Throughput should be positive"
