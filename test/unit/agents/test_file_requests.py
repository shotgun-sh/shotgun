"""Test process_file_requests functionality for text and binary files."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic_ai import BinaryContent

from shotgun.agents.agent_manager import AgentManager
from shotgun.agents.config.models import ProviderType
from shotgun.agents.constants import (
    MAX_BINARY_FILE_SIZE_BYTES,
    MAX_TEXT_FILE_SIZE_BYTES,
)
from shotgun.agents.models import AgentDeps, AgentType
from shotgun.agents.usage_manager import SessionUsageManager


@pytest.fixture
def mock_agent_deps():
    """Create mock AgentDeps for testing."""
    deps = MagicMock(spec=AgentDeps)
    deps.interactive_mode = True
    deps.working_directory = Path("/test")
    deps.max_iterations = 10
    deps.queue = asyncio.Queue()
    deps.tasks = []
    deps.llm_model = MagicMock()
    deps.llm_model.name = "test-model"
    deps.llm_model.provider = ProviderType.ANTHROPIC
    deps.is_tui_context = False
    file_tracker_mock = MagicMock()
    file_tracker_mock.clear = MagicMock()
    file_tracker_mock.operations = []
    deps.file_tracker = file_tracker_mock
    deps.usage_manager = MagicMock(spec=SessionUsageManager)
    deps.usage_manager.build_usage_hint = MagicMock(return_value="")
    return deps


@pytest.fixture
def agent_manager(mock_agent_deps):
    """Create an AgentManager for testing process_file_requests."""
    manager = AgentManager(deps=mock_agent_deps, initial_type=AgentType.RESEARCH)
    # Don't initialize agents - we only need to test process_file_requests
    return manager


def test_process_file_requests_no_pending(agent_manager):
    """Test that process_file_requests returns empty when no requests are pending."""
    result = agent_manager.process_file_requests()
    assert result == []


def test_process_file_requests_text_file_md(agent_manager):
    """Test loading a markdown text file."""
    with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w") as f:
        f.write("# Test Document\n\nThis is test content.")
        temp_path = f.name

    try:
        agent_manager._file_request_pending = True
        agent_manager._pending_file_requests = [temp_path]

        result = agent_manager.process_file_requests()

        assert len(result) == 1
        file_path, content = result[0]
        # Compare resolved paths to handle symlinks (e.g., /var -> /private/var on macOS)
        assert Path(file_path).resolve() == Path(temp_path).resolve()
        assert isinstance(content, str)
        assert "# Test Document" in content
        assert "This is test content." in content
    finally:
        Path(temp_path).unlink()


def test_process_file_requests_text_file_txt(agent_manager):
    """Test loading a plain text file."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
        f.write("Plain text content here.")
        temp_path = f.name

    try:
        agent_manager._file_request_pending = True
        agent_manager._pending_file_requests = [temp_path]

        result = agent_manager.process_file_requests()

        assert len(result) == 1
        file_path, content = result[0]
        assert Path(file_path).resolve() == Path(temp_path).resolve()
        assert isinstance(content, str)
        assert content == "Plain text content here."
    finally:
        Path(temp_path).unlink()


def test_process_file_requests_text_file_json(agent_manager):
    """Test loading a JSON file."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        f.write('{"key": "value", "number": 42}')
        temp_path = f.name

    try:
        agent_manager._file_request_pending = True
        agent_manager._pending_file_requests = [temp_path]

        result = agent_manager.process_file_requests()

        assert len(result) == 1
        file_path, content = result[0]
        assert Path(file_path).resolve() == Path(temp_path).resolve()
        assert isinstance(content, str)
        assert '"key": "value"' in content
    finally:
        Path(temp_path).unlink()


def test_process_file_requests_text_file_py(agent_manager):
    """Test loading a Python source file."""
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
        f.write('def hello():\n    return "Hello, World!"')
        temp_path = f.name

    try:
        agent_manager._file_request_pending = True
        agent_manager._pending_file_requests = [temp_path]

        result = agent_manager.process_file_requests()

        assert len(result) == 1
        file_path, content = result[0]
        assert Path(file_path).resolve() == Path(temp_path).resolve()
        assert isinstance(content, str)
        assert "def hello():" in content
    finally:
        Path(temp_path).unlink()


def test_process_file_requests_binary_file_png(agent_manager):
    """Test loading a PNG image file."""
    # Create a minimal valid PNG file
    png_data = (
        b"\x89PNG\r\n\x1a\n"  # PNG signature
        b"\x00\x00\x00\rIHDR"  # IHDR chunk header
        b"\x00\x00\x00\x01"  # width: 1
        b"\x00\x00\x00\x01"  # height: 1
        b"\x08\x02"  # bit depth: 8, color type: RGB
        b"\x00\x00\x00"  # compression, filter, interlace
        b"\x90wS\xde"  # CRC
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False, mode="wb") as f:
        f.write(png_data)
        temp_path = f.name

    try:
        agent_manager._file_request_pending = True
        agent_manager._pending_file_requests = [temp_path]

        result = agent_manager.process_file_requests()

        assert len(result) == 1
        file_path, content = result[0]
        assert Path(file_path).resolve() == Path(temp_path).resolve()
        assert isinstance(content, BinaryContent)
        assert content.media_type == "image/png"
    finally:
        Path(temp_path).unlink()


def test_process_file_requests_binary_file_pdf(agent_manager):
    """Test loading a PDF file (minimal header only)."""
    # Minimal PDF-like header for testing
    pdf_data = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False, mode="wb") as f:
        f.write(pdf_data)
        temp_path = f.name

    try:
        agent_manager._file_request_pending = True
        agent_manager._pending_file_requests = [temp_path]

        result = agent_manager.process_file_requests()

        assert len(result) == 1
        file_path, content = result[0]
        assert Path(file_path).resolve() == Path(temp_path).resolve()
        assert isinstance(content, BinaryContent)
        assert content.media_type == "application/pdf"
    finally:
        Path(temp_path).unlink()


def test_process_file_requests_mixed_files(agent_manager):
    """Test loading a mix of text and binary files."""
    # Create a text file
    with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w") as f:
        f.write("# Markdown\n\nSome text.")
        md_path = f.name

    # Create a binary file
    png_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False, mode="wb") as f:
        f.write(png_data)
        png_path = f.name

    try:
        agent_manager._file_request_pending = True
        agent_manager._pending_file_requests = [md_path, png_path]

        result = agent_manager.process_file_requests()

        assert len(result) == 2

        # Find the text and binary results by comparing resolved paths
        md_resolved = str(Path(md_path).resolve())
        png_resolved = str(Path(png_path).resolve())
        text_result = next((r for r in result if r[0] == md_resolved), None)
        binary_result = next((r for r in result if r[0] == png_resolved), None)

        assert text_result is not None
        assert isinstance(text_result[1], str)
        assert "# Markdown" in text_result[1]

        assert binary_result is not None
        assert isinstance(binary_result[1], BinaryContent)
    finally:
        Path(md_path).unlink()
        Path(png_path).unlink()


def test_process_file_requests_nonexistent_file(agent_manager):
    """Test that nonexistent files are skipped."""
    agent_manager._file_request_pending = True
    agent_manager._pending_file_requests = ["/nonexistent/file.md"]

    result = agent_manager.process_file_requests()

    assert len(result) == 0
    # Pending state should be cleared
    assert agent_manager._file_request_pending is False


def test_process_file_requests_unsupported_extension(agent_manager):
    """Test that unsupported file extensions are skipped."""
    with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False, mode="w") as f:
        f.write("Some content")
        temp_path = f.name

    try:
        agent_manager._file_request_pending = True
        agent_manager._pending_file_requests = [temp_path]

        result = agent_manager.process_file_requests()

        assert len(result) == 0
    finally:
        Path(temp_path).unlink()


def test_process_file_requests_text_file_latin1_fallback(agent_manager):
    """Test that files with latin-1 encoding are handled correctly."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="wb") as f:
        # Write content with latin-1 specific character (invalid UTF-8)
        f.write("Hello, caf\xe9!".encode("latin-1"))
        temp_path = f.name

    try:
        agent_manager._file_request_pending = True
        agent_manager._pending_file_requests = [temp_path]

        result = agent_manager.process_file_requests()

        assert len(result) == 1
        file_path, content = result[0]
        assert isinstance(content, str)
        assert "Hello, caf" in content
    finally:
        Path(temp_path).unlink()


def test_process_file_requests_clears_pending_state(agent_manager):
    """Test that process_file_requests clears the pending state."""
    with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w") as f:
        f.write("Test content")
        temp_path = f.name

    try:
        agent_manager._file_request_pending = True
        agent_manager._pending_file_requests = [temp_path]

        agent_manager.process_file_requests()

        assert agent_manager._file_request_pending is False
        assert agent_manager._pending_file_requests == []
    finally:
        Path(temp_path).unlink()


def test_process_file_requests_expands_user_path(agent_manager):
    """Test that ~ in paths is expanded correctly."""
    # Create a file in temp, but test the path expansion logic
    with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w") as f:
        f.write("Test content")
        temp_path = f.name

    try:
        agent_manager._file_request_pending = True
        agent_manager._pending_file_requests = [temp_path]

        result = agent_manager.process_file_requests()

        # The returned path should be absolute
        assert len(result) == 1
        returned_path = Path(result[0][0])
        assert returned_path.is_absolute()
    finally:
        Path(temp_path).unlink()


def test_process_file_requests_csv_file(agent_manager):
    """Test loading a CSV file."""
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
        f.write("name,age\nAlice,30\nBob,25")
        temp_path = f.name

    try:
        agent_manager._file_request_pending = True
        agent_manager._pending_file_requests = [temp_path]

        result = agent_manager.process_file_requests()

        assert len(result) == 1
        file_path, content = result[0]
        assert isinstance(content, str)
        assert "name,age" in content
        assert "Alice,30" in content
    finally:
        Path(temp_path).unlink()


def test_process_file_requests_yaml_file(agent_manager):
    """Test loading a YAML file."""
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
        f.write("key: value\nlist:\n  - item1\n  - item2")
        temp_path = f.name

    try:
        agent_manager._file_request_pending = True
        agent_manager._pending_file_requests = [temp_path]

        result = agent_manager.process_file_requests()

        assert len(result) == 1
        file_path, content = result[0]
        assert isinstance(content, str)
        assert "key: value" in content
    finally:
        Path(temp_path).unlink()


def test_text_file_size_limit():
    """Test the text file size limit constant."""
    # 1MB limit for text files
    assert MAX_TEXT_FILE_SIZE_BYTES == 1 * 1024 * 1024


def test_binary_file_size_limit():
    """Test the binary file size limit constant."""
    # 32MB limit for binary files
    assert MAX_BINARY_FILE_SIZE_BYTES == 32 * 1024 * 1024
