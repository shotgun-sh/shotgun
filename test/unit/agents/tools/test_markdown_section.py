"""Tests for replace_markdown_section tool."""

from unittest.mock import MagicMock

import pytest
from pydantic_ai import RunContext

from shotgun.agents.models import AgentDeps, AgentType, FileOperationTracker
from shotgun.agents.tools.markdown_tools import (
    MarkdownHeading,
    extract_headings,
    find_close_matches,
    find_matching_heading,
    find_section_bounds,
    get_heading_level,
    replace_markdown_section,
)


@pytest.fixture
def mock_deps():
    """Create mock dependencies for testing."""
    deps = MagicMock(spec=AgentDeps)
    deps.file_tracker = FileOperationTracker()
    return deps


@pytest.fixture
def mock_context(mock_deps):
    """Create mock run context for testing."""
    ctx = MagicMock(spec=RunContext)
    ctx.deps = mock_deps
    return ctx


class TestGetHeadingLevel:
    """Tests for get_heading_level helper."""

    def test_h1_heading(self):
        assert get_heading_level("# Title") == 1

    def test_h2_heading(self):
        assert get_heading_level("## Section") == 2

    def test_h6_heading(self):
        assert get_heading_level("###### Deep") == 6

    def test_not_heading(self):
        assert get_heading_level("Regular text") is None

    def test_no_space_after_hash(self):
        assert get_heading_level("#NoSpace") is None

    def test_too_many_hashes(self):
        assert get_heading_level("####### Too many") is None


class TestExtractHeadings:
    """Tests for extract_headings helper."""

    def test_extracts_multiple_headings(self):
        content = """# Title
Some content

## Section 1

More content

### Subsection

## Section 2
"""
        headings = extract_headings(content)
        assert len(headings) == 4
        assert headings[0] == MarkdownHeading(line_number=0, text="# Title", level=1)
        assert headings[1] == MarkdownHeading(line_number=3, text="## Section 1", level=2)
        assert headings[2] == MarkdownHeading(line_number=7, text="### Subsection", level=3)
        assert headings[3] == MarkdownHeading(line_number=9, text="## Section 2", level=2)

    def test_empty_content(self):
        assert extract_headings("") == []

    def test_no_headings(self):
        assert extract_headings("Just some text\nwith no headings") == []


class TestFindMatchingHeading:
    """Tests for find_matching_heading helper."""

    def test_exact_match(self):
        headings = [
            MarkdownHeading(line_number=0, text="## Requirements", level=2),
            MarkdownHeading(line_number=5, text="## Technical Notes", level=2),
        ]
        result = find_matching_heading(headings, "## Requirements")
        assert result is not None
        assert result.heading.text == "## Requirements"
        assert result.confidence == 1.0
        assert result.heading.line_number == 0
        assert result.heading.level == 2

    def test_fuzzy_match_typo(self):
        headings = [
            MarkdownHeading(line_number=0, text="## Requirements", level=2),
            MarkdownHeading(line_number=5, text="## Technical Notes", level=2),
        ]
        result = find_matching_heading(headings, "## Requirments")  # typo
        assert result is not None
        assert result.heading.text == "## Requirements"
        assert result.confidence > 0.8
        assert result.heading.line_number == 0

    def test_fuzzy_match_case_insensitive(self):
        headings = [MarkdownHeading(line_number=0, text="## Requirements", level=2)]
        result = find_matching_heading(headings, "## REQUIREMENTS")
        assert result is not None
        assert result.heading.text == "## Requirements"

    def test_no_match_below_threshold(self):
        headings = [MarkdownHeading(line_number=0, text="## Requirements", level=2)]
        result = find_matching_heading(headings, "## Completely Different")
        assert result is None

    def test_hash_count_ignored_in_matching(self):
        headings = [MarkdownHeading(line_number=0, text="## Requirements", level=2)]
        result = find_matching_heading(headings, "### Requirements")
        assert result is not None
        assert result.heading.text == "## Requirements"


class TestFindCloseMatches:
    """Tests for find_close_matches helper."""

    def test_finds_close_matches(self):
        headings = [
            MarkdownHeading(line_number=0, text="## Testing", level=2),
            MarkdownHeading(line_number=5, text="## Test Cases", level=2),
            MarkdownHeading(line_number=10, text="## Implementation", level=2),
        ]
        # "Test" should fuzzy match "Testing" well
        matches = find_close_matches(headings, "## Test", threshold=0.5)
        assert len(matches) >= 1
        match_texts = [m.heading_text for m in matches]
        assert "## Testing" in match_texts

    def test_max_matches(self):
        headings = [
            MarkdownHeading(line_number=0, text="## Testing", level=2),
            MarkdownHeading(line_number=5, text="## Test Cases", level=2),
            MarkdownHeading(line_number=10, text="## Test Plan", level=2),
            MarkdownHeading(line_number=15, text="## Tests", level=2),
        ]
        matches = find_close_matches(headings, "## Test", max_matches=2)
        assert len(matches) <= 2


class TestFindSectionBounds:
    """Tests for find_section_bounds helper."""

    def test_section_ends_at_same_level(self):
        lines = [
            "## Section 1",
            "Content",
            "",
            "## Section 2",
            "More content",
        ]
        start, end = find_section_bounds(lines, 0, 2)
        assert start == 0
        assert end == 3  # Stops before Section 2

    def test_section_ends_at_higher_level(self):
        lines = [
            "## Section",
            "Content",
            "",
            "# Higher Level",
        ]
        start, end = find_section_bounds(lines, 0, 2)
        assert end == 3  # Stops before Higher Level

    def test_section_continues_through_lower_level(self):
        lines = [
            "## Section",
            "Content",
            "### Subsection",
            "More content",
            "## Next Section",
        ]
        start, end = find_section_bounds(lines, 0, 2)
        assert end == 4  # Includes subsection, stops at Next Section

    def test_section_at_eof(self):
        lines = [
            "## Section",
            "Content",
            "More content",
        ]
        start, end = find_section_bounds(lines, 0, 2)
        assert end == 3  # EOF


@pytest.mark.asyncio
async def test_basic_section_replacement(mock_context, tmp_path, monkeypatch):
    """Test basic section replacement."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    # Create initial file
    initial_content = """# Plan

## Requirements

- Old requirement 1
- Old requirement 2

## Technical Notes

Some technical details
"""
    (tmp_path / "plan.md").write_text(initial_content)

    # Replace section
    result = await replace_markdown_section(
        mock_context,
        "plan.md",
        "## Requirements",
        "- New requirement 1\n- New requirement 2\n- New requirement 3",
    )

    assert "Successfully replaced" in result
    assert "## Requirements" in result

    # Verify file content
    new_content = (tmp_path / "plan.md").read_text()
    assert "- New requirement 1" in new_content
    assert "- New requirement 2" in new_content
    assert "- New requirement 3" in new_content
    assert "- Old requirement" not in new_content
    # Ensure other sections preserved
    assert "## Technical Notes" in new_content
    assert "Some technical details" in new_content


@pytest.mark.asyncio
async def test_fuzzy_matching_with_typo(mock_context, tmp_path, monkeypatch):
    """Test that fuzzy matching catches typos."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Plan

## Requirements

Old content
"""
    (tmp_path / "plan.md").write_text(initial_content)

    # Use typo in section heading
    result = await replace_markdown_section(
        mock_context,
        "plan.md",
        "## Requirments",  # typo
        "New content",
    )

    assert "Successfully replaced" in result
    # Check confidence is shown
    assert "%" in result


@pytest.mark.asyncio
async def test_section_at_end_of_file(mock_context, tmp_path, monkeypatch):
    """Test replacing a section at the end of file."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Plan

## First Section

Some content

## Last Section

Old last content
"""
    (tmp_path / "plan.md").write_text(initial_content)

    result = await replace_markdown_section(
        mock_context,
        "plan.md",
        "## Last Section",
        "New last content",
    )

    assert "Successfully replaced" in result
    new_content = (tmp_path / "plan.md").read_text()
    assert "New last content" in new_content
    assert "Old last content" not in new_content
    assert "## First Section" in new_content


@pytest.mark.asyncio
async def test_heading_rename(mock_context, tmp_path, monkeypatch):
    """Test renaming a section heading."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Plan

## Old Name

Content
"""
    (tmp_path / "plan.md").write_text(initial_content)

    result = await replace_markdown_section(
        mock_context,
        "plan.md",
        "## Old Name",
        "Content",
        new_heading="## New Name",
    )

    assert "Successfully replaced" in result
    new_content = (tmp_path / "plan.md").read_text()
    assert "## New Name" in new_content
    assert "## Old Name" not in new_content


@pytest.mark.asyncio
async def test_no_match_returns_available_headings(mock_context, tmp_path, monkeypatch):
    """Test that no match returns helpful error with available headings."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Plan

## Requirements

Content

## Technical Notes

More content
"""
    (tmp_path / "plan.md").write_text(initial_content)

    result = await replace_markdown_section(
        mock_context,
        "plan.md",
        "## Nonexistent Section",
        "New content",
    )

    assert "No section matching" in result
    assert "plan.md" in result


@pytest.mark.asyncio
async def test_file_not_found(mock_context, tmp_path, monkeypatch):
    """Test file not found error."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    result = await replace_markdown_section(
        mock_context,
        "plan.md",
        "## Section",
        "Content",
    )

    assert "Error" in result
    assert "not found" in result


@pytest.mark.asyncio
async def test_no_headings_in_file(mock_context, tmp_path, monkeypatch):
    """Test error when file has no headings."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    (tmp_path / "plan.md").write_text("Just some text without headings")

    result = await replace_markdown_section(
        mock_context,
        "plan.md",
        "## Section",
        "Content",
    )

    assert "Error" in result
    assert "No headings found" in result


@pytest.mark.asyncio
async def test_agent_scoping_restrictions(mock_context, tmp_path, monkeypatch):
    """Test that agent scoping restrictions are enforced."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    # Create a file the plan agent can't write to
    (tmp_path / "research.md").write_text("# Research\n\n## Findings\n\nData")

    result = await replace_markdown_section(
        mock_context,
        "research.md",
        "## Findings",
        "New findings",
    )

    assert "Error" in result
    assert "Plan agent can only write to" in result


@pytest.mark.asyncio
async def test_file_operation_tracking(mock_context, tmp_path, monkeypatch):
    """Test that file operations are tracked."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    (tmp_path / "plan.md").write_text("# Plan\n\n## Section\n\nContent")

    await replace_markdown_section(
        mock_context,
        "plan.md",
        "## Section",
        "New content",
    )

    # Verify file operation was tracked
    assert len(mock_context.deps.file_tracker.operations) == 1


@pytest.mark.asyncio
async def test_empty_section(mock_context, tmp_path, monkeypatch):
    """Test replacing an empty section (heading followed by heading)."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Plan

## Empty Section
## Next Section

Content
"""
    (tmp_path / "plan.md").write_text(initial_content)

    result = await replace_markdown_section(
        mock_context,
        "plan.md",
        "## Empty Section",
        "Now has content",
    )

    assert "Successfully replaced" in result
    new_content = (tmp_path / "plan.md").read_text()
    assert "Now has content" in new_content
    assert "## Next Section" in new_content


@pytest.mark.asyncio
async def test_subsections_replaced_with_parent(mock_context, tmp_path, monkeypatch):
    """Test that subsections are replaced when parent section is replaced."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Plan

## Parent Section

Intro

### Child Section 1

Child 1 content

### Child Section 2

Child 2 content

## Next Section

Other content
"""
    (tmp_path / "plan.md").write_text(initial_content)

    result = await replace_markdown_section(
        mock_context,
        "plan.md",
        "## Parent Section",
        "Completely new content without subsections",
    )

    assert "Successfully replaced" in result
    new_content = (tmp_path / "plan.md").read_text()
    assert "Completely new content without subsections" in new_content
    assert "### Child Section" not in new_content
    assert "## Next Section" in new_content


@pytest.mark.asyncio
async def test_crlf_line_endings_preserved(mock_context, tmp_path, monkeypatch):
    """Test that CRLF line endings are preserved."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = "# Plan\r\n\r\n## Section\r\n\r\nOld content\r\n"
    (tmp_path / "plan.md").write_bytes(initial_content.encode("utf-8"))

    result = await replace_markdown_section(
        mock_context,
        "plan.md",
        "## Section",
        "New content",
    )

    assert "Successfully replaced" in result
    new_content = (tmp_path / "plan.md").read_bytes().decode("utf-8")
    assert "\r\n" in new_content


@pytest.mark.asyncio
async def test_research_agent_can_replace_in_research_md(
    mock_context, tmp_path, monkeypatch
):
    """Test that research agent can replace sections in research.md."""
    mock_context.deps.agent_mode = AgentType.RESEARCH
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    (tmp_path / "research.md").write_text("# Research\n\n## Findings\n\nOld data")

    result = await replace_markdown_section(
        mock_context,
        "research.md",
        "## Findings",
        "New research findings",
    )

    assert "Successfully replaced" in result


@pytest.mark.asyncio
async def test_export_agent_can_replace_in_non_protected_files(
    mock_context, tmp_path, monkeypatch
):
    """Test that export agent can replace sections in non-protected files."""
    mock_context.deps.agent_mode = AgentType.EXPORT
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    (tmp_path / "custom.md").write_text("# Custom\n\n## Section\n\nContent")

    result = await replace_markdown_section(
        mock_context,
        "custom.md",
        "## Section",
        "New content",
    )

    assert "Successfully replaced" in result


@pytest.mark.asyncio
async def test_export_agent_cannot_replace_protected_files(
    mock_context, tmp_path, monkeypatch
):
    """Test that export agent cannot replace sections in protected files."""
    mock_context.deps.agent_mode = AgentType.EXPORT
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    (tmp_path / "research.md").write_text("# Research\n\n## Section\n\nContent")

    result = await replace_markdown_section(
        mock_context,
        "research.md",
        "## Section",
        "New content",
    )

    assert "Error" in result
    assert "cannot write to protected file" in result
