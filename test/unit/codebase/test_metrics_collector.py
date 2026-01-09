"""Unit tests for MetricsCollector class."""

import csv
import json
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from shotgun.codebase.core.metrics_collector import MetricsCollector
from shotgun.codebase.core.metrics_types import (
    FileParseMetrics,
    IndexingMetrics,
    WorkerMetrics,
)


class TestMetricsCollectorBasics:
    """Basic functionality tests."""

    def test_initialization(self) -> None:
        """Test MetricsCollector initializes with correct defaults."""
        collector = MetricsCollector("test-codebase")

        assert collector._codebase_name == "test-codebase"
        assert collector._collect_file_metrics is True
        assert collector._collect_worker_metrics is True
        assert len(collector._session_id) == 36  # UUID format
        assert collector._total_nodes == 0
        assert collector._total_relationships == 0

    def test_initialization_with_options(self) -> None:
        """Test MetricsCollector respects initialization options."""
        collector = MetricsCollector(
            "test-codebase",
            collect_file_metrics=False,
            collect_worker_metrics=False,
        )

        assert collector._collect_file_metrics is False
        assert collector._collect_worker_metrics is False


class TestPhaseMetrics:
    """Tests for phase timing functionality."""

    def test_phase_timing_records_duration(self) -> None:
        """Test that phase timing records approximate duration."""
        collector = MetricsCollector("test-codebase")

        collector.start_phase("test_phase")
        time.sleep(0.1)  # Sleep 100ms
        collector.end_phase("test_phase", 100)

        metrics = collector.get_metrics()
        assert "test_phase" in metrics.phase_metrics

        phase = metrics.phase_metrics["test_phase"]
        assert phase.duration_seconds >= 0.09  # Allow some timing variance
        assert phase.duration_seconds < 0.5  # But not too long
        assert phase.items_processed == 100

    def test_phase_throughput_calculation(self) -> None:
        """Test that throughput is correctly calculated."""
        collector = MetricsCollector("test-codebase")

        collector.start_phase("test_phase")
        time.sleep(0.1)
        collector.end_phase("test_phase", 50)

        metrics = collector.get_metrics()
        phase = metrics.phase_metrics["test_phase"]

        # 50 items in ~0.1 seconds = ~500 items/sec
        assert phase.throughput > 100  # At least 100 items/sec
        assert phase.throughput < 1000  # But not more than 1000

    def test_multiple_phases(self) -> None:
        """Test collecting metrics for multiple phases."""
        collector = MetricsCollector("test-codebase")

        phases = ["structure", "definitions", "relationships"]
        for phase_name in phases:
            collector.start_phase(phase_name)
            time.sleep(0.01)
            collector.end_phase(phase_name, 10)

        metrics = collector.get_metrics()
        assert len(metrics.phase_metrics) == 3
        for phase_name in phases:
            assert phase_name in metrics.phase_metrics

    def test_end_phase_without_start_is_noop(self) -> None:
        """Test that ending a phase without starting it does nothing."""
        collector = MetricsCollector("test-codebase")

        collector.end_phase("nonexistent_phase", 100)

        metrics = collector.get_metrics()
        assert "nonexistent_phase" not in metrics.phase_metrics


class TestMemoryTracking:
    """Tests for memory tracking functionality."""

    def test_memory_tracking_returns_positive_value(self) -> None:
        """Test that memory tracking returns a positive value."""
        collector = MetricsCollector("test-codebase")

        memory = collector._get_memory_mb()
        assert isinstance(memory, float)
        assert memory > 0  # Should have some memory usage

    def test_memory_recorded_in_phase_metrics(self) -> None:
        """Test that memory is recorded in phase metrics."""
        collector = MetricsCollector("test-codebase")

        collector.start_phase("test_phase")
        collector.end_phase("test_phase", 10)

        metrics = collector.get_metrics()
        phase = metrics.phase_metrics["test_phase"]
        assert phase.memory_mb >= 0

    @patch("psutil.Process")
    def test_memory_tracking_handles_exception(self, mock_process: MagicMock) -> None:
        """Test that memory tracking handles exceptions gracefully."""
        mock_process.side_effect = Exception("Process error")

        collector = MetricsCollector("test-codebase")
        memory = collector._get_memory_mb()

        assert memory == 0.0


class TestFileMetrics:
    """Tests for file-level metrics collection."""

    def test_file_metrics_collection(self) -> None:
        """Test that file metrics are collected."""
        collector = MetricsCollector("test-codebase")

        file_metrics = FileParseMetrics(
            file_path="src/test.py",
            language="python",
            file_size_bytes=1024,
            parse_time_ms=5.5,
            ast_nodes=100,
            definitions_extracted=10,
            relationships_found=5,
        )
        collector.record_file_parse(file_metrics)

        metrics = collector.get_metrics()
        assert len(metrics.file_metrics) == 1
        assert metrics.file_metrics[0].file_path == "src/test.py"

    def test_file_metrics_not_collected_when_disabled(self) -> None:
        """Test that file metrics are not collected when disabled."""
        collector = MetricsCollector("test-codebase", collect_file_metrics=False)

        file_metrics = FileParseMetrics(
            file_path="src/test.py",
            language="python",
            file_size_bytes=1024,
            parse_time_ms=5.5,
            ast_nodes=100,
            definitions_extracted=10,
            relationships_found=5,
        )
        collector.record_file_parse(file_metrics)

        metrics = collector.get_metrics()
        assert len(metrics.file_metrics) == 0


class TestWorkerMetrics:
    """Tests for worker-level metrics collection."""

    def test_worker_metrics_collection(self) -> None:
        """Test that worker metrics are collected."""
        collector = MetricsCollector("test-codebase")

        worker_metrics = WorkerMetrics(
            worker_id=0,
            files_processed=50,
            nodes_created=200,
            relationships_created=100,
            duration_seconds=5.0,
            throughput=10.0,
            peak_memory_mb=100.0,
            idle_time_seconds=0.5,
        )
        collector.record_worker_metrics(0, worker_metrics)

        # Worker metrics are stored internally but not directly exposed
        assert collector._worker_metrics[0].files_processed == 50

    def test_worker_metrics_not_collected_when_disabled(self) -> None:
        """Test that worker metrics are not collected when disabled."""
        collector = MetricsCollector("test-codebase", collect_worker_metrics=False)

        worker_metrics = WorkerMetrics(
            worker_id=0,
            files_processed=50,
            nodes_created=200,
            relationships_created=100,
            duration_seconds=5.0,
            throughput=10.0,
            peak_memory_mb=100.0,
            idle_time_seconds=0.5,
        )
        collector.record_worker_metrics(0, worker_metrics)

        assert len(collector._worker_metrics) == 0


class TestThreadSafety:
    """Tests for thread-safe operations."""

    def test_concurrent_file_metrics_recording(self) -> None:
        """Test that concurrent file metrics recording is thread-safe."""
        collector = MetricsCollector("test-codebase")
        num_threads = 10
        files_per_thread = 100

        def record_files(thread_id: int) -> None:
            for i in range(files_per_thread):
                file_metrics = FileParseMetrics(
                    file_path=f"src/file_{thread_id}_{i}.py",
                    language="python",
                    file_size_bytes=1024,
                    parse_time_ms=1.0,
                    ast_nodes=50,
                    definitions_extracted=5,
                    relationships_found=2,
                )
                collector.record_file_parse(file_metrics)

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=record_files, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        metrics = collector.get_metrics()
        expected_count = num_threads * files_per_thread
        assert len(metrics.file_metrics) == expected_count

    def test_concurrent_phase_operations(self) -> None:
        """Test that concurrent phase operations are thread-safe."""
        collector = MetricsCollector("test-codebase")
        num_threads = 5

        def run_phase(thread_id: int) -> None:
            phase_name = f"phase_{thread_id}"
            collector.start_phase(phase_name)
            time.sleep(0.01)
            collector.end_phase(phase_name, 10)

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=run_phase, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        metrics = collector.get_metrics()
        assert len(metrics.phase_metrics) == num_threads


class TestGetMetrics:
    """Tests for the get_metrics method."""

    def test_get_metrics_returns_complete_structure(self) -> None:
        """Test that get_metrics returns a complete IndexingMetrics object."""
        collector = MetricsCollector("test-codebase")

        # Run through a simple workflow
        collector.start_phase("structure")
        collector.end_phase("structure", 10)
        collector.start_phase("definitions")
        collector.end_phase("definitions", 50)
        collector.set_totals(nodes=100, relationships=200)

        metrics = collector.get_metrics()

        assert isinstance(metrics, IndexingMetrics)
        assert metrics.codebase_name == "test-codebase"
        assert len(metrics.session_id) == 36
        assert metrics.total_duration_seconds > 0
        assert metrics.total_nodes == 100
        assert metrics.total_relationships == 200
        assert metrics.total_files == 50  # From definitions phase

    def test_get_metrics_calculates_peak_memory(self) -> None:
        """Test that get_metrics calculates peak memory across phases."""
        collector = MetricsCollector("test-codebase")

        collector.start_phase("phase1")
        collector.end_phase("phase1", 10)
        collector.start_phase("phase2")
        collector.end_phase("phase2", 20)

        metrics = collector.get_metrics()
        assert metrics.peak_memory_mb > 0


class TestExportJson:
    """Tests for JSON export functionality."""

    def test_export_json_creates_valid_file(self) -> None:
        """Test that export_json creates a valid JSON file."""
        collector = MetricsCollector("test-codebase")

        collector.start_phase("test")
        collector.end_phase("test", 10)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = Path(f.name)

        try:
            collector.export_json(temp_path)

            content = temp_path.read_text()
            data = json.loads(content)

            assert data["codebase_name"] == "test-codebase"
            assert "phase_metrics" in data
            assert "test" in data["phase_metrics"]
        finally:
            temp_path.unlink()

    def test_export_json_structure_matches_indexing_metrics(self) -> None:
        """Test that exported JSON can be parsed as IndexingMetrics."""
        collector = MetricsCollector("test-codebase")

        collector.start_phase("definitions")
        collector.end_phase("definitions", 50)
        collector.set_totals(100, 200)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = Path(f.name)

        try:
            collector.export_json(temp_path)

            content = temp_path.read_text()
            data = json.loads(content)

            # Verify all required fields are present
            required_fields = [
                "session_id",
                "codebase_name",
                "total_duration_seconds",
                "phase_metrics",
                "file_metrics",
                "total_files",
                "total_nodes",
                "total_relationships",
                "avg_throughput",
                "peak_memory_mb",
            ]
            for field in required_fields:
                assert field in data, f"Missing field: {field}"
        finally:
            temp_path.unlink()


class TestExportCsv:
    """Tests for CSV export functionality."""

    def test_export_csv_creates_valid_file(self) -> None:
        """Test that export_csv creates a parseable CSV file."""
        collector = MetricsCollector("test-codebase")

        collector.start_phase("structure")
        collector.end_phase("structure", 10)
        collector.start_phase("definitions")
        collector.end_phase("definitions", 50)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_path = Path(f.name)

        try:
            collector.export_csv(temp_path)

            with temp_path.open() as f:
                reader = csv.reader(f)
                rows = list(reader)

            # Check header section exists
            assert any("Indexing Metrics" in str(row) for row in rows)
            # Check phase metrics section exists
            assert any("Phase Metrics" in str(row) for row in rows)
        finally:
            temp_path.unlink()

    def test_export_csv_includes_file_metrics(self) -> None:
        """Test that CSV export includes file metrics when collected."""
        collector = MetricsCollector("test-codebase")

        file_metrics = FileParseMetrics(
            file_path="src/test.py",
            language="python",
            file_size_bytes=1024,
            parse_time_ms=5.5,
            ast_nodes=100,
            definitions_extracted=10,
            relationships_found=5,
        )
        collector.record_file_parse(file_metrics)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_path = Path(f.name)

        try:
            collector.export_csv(temp_path)

            content = temp_path.read_text()
            assert "File Metrics" in content
            assert "src/test.py" in content
        finally:
            temp_path.unlink()


class TestSetTotals:
    """Tests for the set_totals method."""

    def test_set_totals_updates_values(self) -> None:
        """Test that set_totals updates node and relationship counts."""
        collector = MetricsCollector("test-codebase")

        collector.set_totals(nodes=500, relationships=1000)

        metrics = collector.get_metrics()
        assert metrics.total_nodes == 500
        assert metrics.total_relationships == 1000
