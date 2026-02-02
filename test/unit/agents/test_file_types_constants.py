"""Test file type constants and helper functions."""

from shotgun.agents.constants import (
    BINARY_EXTENSIONS,
    MAX_BINARY_FILE_SIZE_BYTES,
    MAX_TEXT_FILE_SIZE_BYTES,
    MIME_TYPES,
    TEXT_EXTENSIONS,
    get_mime_type,
    is_binary_extension,
    is_supported_extension,
    is_text_extension,
)


def test_binary_extensions_contains_expected():
    """Test that BINARY_EXTENSIONS contains the expected file types."""
    expected = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp"}
    assert expected <= BINARY_EXTENSIONS


def test_text_extensions_contains_common_types():
    """Test that TEXT_EXTENSIONS contains common text file types."""
    common_types = {".md", ".txt", ".json", ".yaml", ".yml", ".py", ".js", ".ts"}
    assert common_types <= TEXT_EXTENSIONS


def test_text_extensions_contains_config_files():
    """Test that TEXT_EXTENSIONS contains config file types."""
    config_types = {".toml", ".ini", ".cfg", ".conf", ".env"}
    assert config_types <= TEXT_EXTENSIONS


def test_text_extensions_contains_programming_languages():
    """Test that TEXT_EXTENSIONS contains various programming language files."""
    language_types = {".java", ".go", ".rs", ".rb", ".php", ".c", ".cpp"}
    assert language_types <= TEXT_EXTENSIONS


def test_is_binary_extension_pdf():
    """Test is_binary_extension for PDF."""
    assert is_binary_extension(".pdf") is True
    assert is_binary_extension(".PDF") is True


def test_is_binary_extension_images():
    """Test is_binary_extension for image formats."""
    assert is_binary_extension(".png") is True
    assert is_binary_extension(".jpg") is True
    assert is_binary_extension(".jpeg") is True
    assert is_binary_extension(".gif") is True
    assert is_binary_extension(".webp") is True


def test_is_binary_extension_text_files_are_false():
    """Test that text files return False for is_binary_extension."""
    assert is_binary_extension(".md") is False
    assert is_binary_extension(".txt") is False
    assert is_binary_extension(".py") is False
    assert is_binary_extension(".json") is False


def test_is_text_extension_common_types():
    """Test is_text_extension for common text types."""
    assert is_text_extension(".md") is True
    assert is_text_extension(".txt") is True
    assert is_text_extension(".json") is True
    assert is_text_extension(".yaml") is True
    assert is_text_extension(".py") is True


def test_is_text_extension_case_insensitive():
    """Test is_text_extension is case insensitive."""
    assert is_text_extension(".MD") is True
    assert is_text_extension(".TXT") is True
    assert is_text_extension(".Json") is True


def test_is_text_extension_binary_files_are_false():
    """Test that binary files return False for is_text_extension."""
    assert is_text_extension(".pdf") is False
    assert is_text_extension(".png") is False
    assert is_text_extension(".jpg") is False


def test_is_supported_extension_text():
    """Test is_supported_extension for text files."""
    assert is_supported_extension(".md") is True
    assert is_supported_extension(".txt") is True
    assert is_supported_extension(".py") is True


def test_is_supported_extension_binary():
    """Test is_supported_extension for binary files."""
    assert is_supported_extension(".pdf") is True
    assert is_supported_extension(".png") is True


def test_is_supported_extension_unknown():
    """Test is_supported_extension for unknown extensions."""
    assert is_supported_extension(".xyz") is False
    assert is_supported_extension(".foo") is False
    assert is_supported_extension(".bar") is False


def test_get_mime_type_pdf():
    """Test get_mime_type for PDF."""
    assert get_mime_type(".pdf") == "application/pdf"


def test_get_mime_type_images():
    """Test get_mime_type for image formats."""
    assert get_mime_type(".png") == "image/png"
    assert get_mime_type(".jpg") == "image/jpeg"
    assert get_mime_type(".jpeg") == "image/jpeg"
    assert get_mime_type(".gif") == "image/gif"
    assert get_mime_type(".webp") == "image/webp"


def test_get_mime_type_case_insensitive():
    """Test get_mime_type is case insensitive."""
    assert get_mime_type(".PDF") == "application/pdf"
    assert get_mime_type(".PNG") == "image/png"


def test_get_mime_type_text_returns_none():
    """Test get_mime_type returns None for text files."""
    assert get_mime_type(".md") is None
    assert get_mime_type(".txt") is None
    assert get_mime_type(".py") is None


def test_get_mime_type_unknown_returns_none():
    """Test get_mime_type returns None for unknown extensions."""
    assert get_mime_type(".xyz") is None
    assert get_mime_type(".foo") is None


def test_mime_types_dict_consistency():
    """Test that MIME_TYPES dict contains all binary extensions."""
    for ext in BINARY_EXTENSIONS:
        assert ext in MIME_TYPES, f"{ext} is in BINARY_EXTENSIONS but not in MIME_TYPES"


def test_no_overlap_between_binary_and_text():
    """Test that binary and text extensions don't overlap."""
    overlap = BINARY_EXTENSIONS & TEXT_EXTENSIONS
    assert overlap == set(), f"Extensions should not be in both: {overlap}"


def test_max_binary_file_size():
    """Test MAX_BINARY_FILE_SIZE_BYTES is 32MB."""
    assert MAX_BINARY_FILE_SIZE_BYTES == 32 * 1024 * 1024


def test_max_text_file_size():
    """Test MAX_TEXT_FILE_SIZE_BYTES is 1MB."""
    assert MAX_TEXT_FILE_SIZE_BYTES == 1 * 1024 * 1024


def test_extensions_are_frozenset():
    """Test that extension sets are frozensets (immutable)."""
    assert isinstance(BINARY_EXTENSIONS, frozenset)
    assert isinstance(TEXT_EXTENSIONS, frozenset)


def test_extensions_start_with_dot():
    """Test that all extensions start with a dot."""
    for ext in BINARY_EXTENSIONS:
        assert ext.startswith("."), f"Extension {ext} should start with a dot"
    for ext in TEXT_EXTENSIONS:
        assert ext.startswith("."), f"Extension {ext} should start with a dot"
