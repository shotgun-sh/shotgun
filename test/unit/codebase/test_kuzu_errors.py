"""Unit tests for Kuzu error classification."""

from pathlib import Path

from shotgun.codebase.core.errors import (
    DatabaseCorruptedError,
    DatabaseIssue,
    DatabaseLockedError,
    DatabaseSchemaError,
    DatabaseTimeoutError,
    KuzuErrorType,
    classify_kuzu_error,
)


class TestClassifyKuzuError:
    """Test cases for classify_kuzu_error function."""

    def test_classify_locked_error(self):
        """Lock contention error should be classified as LOCKED."""
        error = RuntimeError(
            "IO exception: Could not set lock on file : /path/to/db.kuzu"
        )
        assert classify_kuzu_error(error) == KuzuErrorType.LOCKED

    def test_classify_corruption_unable_to_open(self):
        """Unable to open database error should be classified as CORRUPTION."""
        error = RuntimeError(
            "Runtime exception: Unable to open database at /path/to/db"
        )
        assert classify_kuzu_error(error) == KuzuErrorType.CORRUPTION

    def test_classify_corruption_reading_past_end(self):
        """Reading past end of file error should be classified as CORRUPTION."""
        error = RuntimeError(
            "Runtime exception: Reading past the end of the file /path/to/db with size 123"
        )
        assert classify_kuzu_error(error) == KuzuErrorType.CORRUPTION

    def test_classify_corruption_invalid_database(self):
        """Invalid database file error should be classified as CORRUPTION."""
        error = RuntimeError(
            "Runtime exception: Unable to open database. The file is not a valid Lbug database file!"
        )
        assert classify_kuzu_error(error) == KuzuErrorType.CORRUPTION

    def test_classify_corruption_unordered_map(self):
        """C++ unordered_map error should be classified as CORRUPTION."""
        error = RuntimeError("std::exception: unordered_map::at key not found")
        assert classify_kuzu_error(error) == KuzuErrorType.CORRUPTION

    def test_classify_corruption_key_not_found(self):
        """Key not found error should be classified as CORRUPTION."""
        error = RuntimeError("key not found in internal data structure")
        assert classify_kuzu_error(error) == KuzuErrorType.CORRUPTION

    def test_classify_corruption_std_exception(self):
        """std::exception error should be classified as CORRUPTION."""
        error = RuntimeError("std::exception thrown during database operation")
        assert classify_kuzu_error(error) == KuzuErrorType.CORRUPTION

    def test_classify_permission_denied(self):
        """Permission denied error should be classified as PERMISSION."""
        error = RuntimeError(
            "IO exception: Cannot open file /path/to/db: Permission denied"
        )
        assert classify_kuzu_error(error) == KuzuErrorType.PERMISSION

    def test_classify_missing_file(self):
        """File not found error should be classified as MISSING."""
        error = RuntimeError(
            "IO exception: Cannot open file /path/to/db: No such file or directory"
        )
        assert classify_kuzu_error(error) == KuzuErrorType.MISSING

    def test_classify_schema_table_not_exist(self):
        """Table does not exist error should be classified as SCHEMA."""
        error = RuntimeError("Binder exception: Table Project does not exist.")
        assert classify_kuzu_error(error) == KuzuErrorType.SCHEMA

    def test_classify_schema_generic_table_error(self):
        """Generic table does not exist error should be classified as SCHEMA."""
        error = RuntimeError("Table MyTable does not exist in the database")
        assert classify_kuzu_error(error) == KuzuErrorType.SCHEMA

    def test_classify_unknown_error(self):
        """Unknown error should be classified as UNKNOWN."""
        error = RuntimeError("Some completely unexpected error occurred")
        assert classify_kuzu_error(error) == KuzuErrorType.UNKNOWN

    def test_classify_non_runtime_error(self):
        """Non-RuntimeError exceptions should still be classified."""
        error = ValueError("Invalid value in database")
        assert classify_kuzu_error(error) == KuzuErrorType.UNKNOWN

    def test_classify_exception_with_empty_message(self):
        """Empty error message should be classified as UNKNOWN."""
        error = RuntimeError("")
        assert classify_kuzu_error(error) == KuzuErrorType.UNKNOWN


class TestDatabaseIssue:
    """Test cases for DatabaseIssue model."""

    def test_create_database_issue(self):
        """DatabaseIssue should be created with all fields."""
        issue = DatabaseIssue(
            graph_id="test-graph",
            graph_path=Path("/path/to/test.kuzu"),
            error_type=KuzuErrorType.LOCKED,
            message="Database is locked",
        )
        assert issue.graph_id == "test-graph"
        assert issue.graph_path == Path("/path/to/test.kuzu")
        assert issue.error_type == KuzuErrorType.LOCKED
        assert issue.message == "Database is locked"


class TestDatabaseExceptions:
    """Test cases for custom database exception classes."""

    def test_database_locked_error(self):
        """DatabaseLockedError should have correct attributes."""
        error = DatabaseLockedError(
            graph_id="test-graph",
            graph_path="/path/to/test.kuzu",
        )
        assert error.graph_id == "test-graph"
        assert error.graph_path == "/path/to/test.kuzu"
        assert error.error_type == KuzuErrorType.LOCKED
        assert "locked" in str(error).lower()
        assert "another process" in str(error).lower()

    def test_database_corrupted_error(self):
        """DatabaseCorruptedError should have correct attributes."""
        error = DatabaseCorruptedError(
            graph_id="test-graph",
            graph_path="/path/to/test.kuzu",
            details="Invalid header",
        )
        assert error.graph_id == "test-graph"
        assert error.graph_path == "/path/to/test.kuzu"
        assert error.error_type == KuzuErrorType.CORRUPTION
        assert "corrupted" in str(error).lower()
        assert "Invalid header" in str(error)

    def test_database_corrupted_error_no_details(self):
        """DatabaseCorruptedError without details should still work."""
        error = DatabaseCorruptedError(
            graph_id="test-graph",
            graph_path="/path/to/test.kuzu",
        )
        assert "corrupted" in str(error).lower()

    def test_database_schema_error(self):
        """DatabaseSchemaError should have correct attributes."""
        error = DatabaseSchemaError(
            graph_id="test-graph",
            graph_path="/path/to/test.kuzu",
        )
        assert error.graph_id == "test-graph"
        assert error.graph_path == "/path/to/test.kuzu"
        assert error.error_type == KuzuErrorType.SCHEMA
        assert "incomplete schema" in str(error).lower()

    def test_database_timeout_error(self):
        """DatabaseTimeoutError should have correct attributes."""
        error = DatabaseTimeoutError(
            graph_id="test-graph",
            graph_path="/path/to/test.kuzu",
            timeout_seconds=10.0,
        )
        assert error.graph_id == "test-graph"
        assert error.graph_path == "/path/to/test.kuzu"
        assert error.error_type == KuzuErrorType.TIMEOUT
        assert error.timeout_seconds == 10.0
        assert "10" in str(error)
        assert "timed out" in str(error).lower()


class TestKuzuErrorType:
    """Test cases for KuzuErrorType enum."""

    def test_error_type_values(self):
        """KuzuErrorType should have expected string values."""
        assert KuzuErrorType.LOCKED == "locked"
        assert KuzuErrorType.CORRUPTION == "corruption"
        assert KuzuErrorType.PERMISSION == "permission"
        assert KuzuErrorType.MISSING == "missing"
        assert KuzuErrorType.SCHEMA == "schema"
        assert KuzuErrorType.TIMEOUT == "timeout"
        assert KuzuErrorType.UNKNOWN == "unknown"

    def test_error_type_is_str_enum(self):
        """KuzuErrorType should be usable as a string."""
        assert str(KuzuErrorType.LOCKED) == "locked"
        assert f"Error type: {KuzuErrorType.CORRUPTION}" == "Error type: corruption"
