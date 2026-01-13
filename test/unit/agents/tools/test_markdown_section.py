"""Tests for replace_markdown_section tool."""

from unittest.mock import MagicMock

import pytest
from pydantic_ai import RunContext

from shotgun.agents.models import AgentDeps, AgentType, FileOperationTracker
from shotgun.agents.tools.markdown_tools import (
    MarkdownHeading,
    SectionNumber,
    decrement_section_number,
    extract_headings,
    find_close_matches,
    find_matching_heading,
    find_section_bounds,
    get_heading_level,
    increment_section_number,
    insert_markdown_section,
    parse_section_number,
    remove_markdown_section,
    renumber_headings_after,
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
        assert headings[1] == MarkdownHeading(
            line_number=3, text="## Section 1", level=2
        )
        assert headings[2] == MarkdownHeading(
            line_number=7, text="### Subsection", level=3
        )
        assert headings[3] == MarkdownHeading(
            line_number=9, text="## Section 2", level=2
        )

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


# =============================================================================
# Tests for insert_markdown_section
# =============================================================================


@pytest.mark.asyncio
async def test_basic_insert(mock_context, tmp_path, monkeypatch):
    """Test basic content insertion at end of section."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Plan

## Requirements

- Existing req 1
- Existing req 2

## Technical Notes

Some technical details
"""
    (tmp_path / "plan.md").write_text(initial_content)

    result = await insert_markdown_section(
        mock_context,
        "plan.md",
        "## Requirements",
        "- New req 3\n- New req 4",
    )

    assert "Successfully inserted" in result
    assert "## Requirements" in result

    new_content = (tmp_path / "plan.md").read_text()
    # Original content preserved
    assert "- Existing req 1" in new_content
    assert "- Existing req 2" in new_content
    # New content added
    assert "- New req 3" in new_content
    assert "- New req 4" in new_content
    # Other sections preserved
    assert "## Technical Notes" in new_content
    assert "Some technical details" in new_content


@pytest.mark.asyncio
async def test_insert_with_new_heading(mock_context, tmp_path, monkeypatch):
    """Test insertion with a new subsection heading."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Plan

## Requirements

- Existing req

## Notes
"""
    (tmp_path / "plan.md").write_text(initial_content)

    result = await insert_markdown_section(
        mock_context,
        "plan.md",
        "## Requirements",
        "- Technical req 1",
        new_heading="### Technical Requirements",
    )

    assert "Successfully inserted" in result
    assert "### Technical Requirements" in result

    new_content = (tmp_path / "plan.md").read_text()
    assert "### Technical Requirements" in new_content
    assert "- Technical req 1" in new_content
    assert "- Existing req" in new_content


@pytest.mark.asyncio
async def test_insert_at_eof(mock_context, tmp_path, monkeypatch):
    """Test insertion into section at end of file."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Plan

## Last Section

Existing content
"""
    (tmp_path / "plan.md").write_text(initial_content)

    result = await insert_markdown_section(
        mock_context,
        "plan.md",
        "## Last Section",
        "New appended content",
    )

    assert "Successfully inserted" in result
    new_content = (tmp_path / "plan.md").read_text()
    assert "Existing content" in new_content
    assert "New appended content" in new_content


@pytest.mark.asyncio
async def test_insert_into_empty_section(mock_context, tmp_path, monkeypatch):
    """Test insertion into an empty section."""
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

    result = await insert_markdown_section(
        mock_context,
        "plan.md",
        "## Empty Section",
        "Now has content",
    )

    assert "Successfully inserted" in result
    new_content = (tmp_path / "plan.md").read_text()
    assert "Now has content" in new_content
    assert "## Next Section" in new_content


@pytest.mark.asyncio
async def test_insert_fuzzy_matching(mock_context, tmp_path, monkeypatch):
    """Test that fuzzy matching works for insert."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Plan

## Requirements

Existing
"""
    (tmp_path / "plan.md").write_text(initial_content)

    result = await insert_markdown_section(
        mock_context,
        "plan.md",
        "## Requirments",  # typo
        "New content",
    )

    assert "Successfully inserted" in result
    assert "%" in result  # confidence shown


@pytest.mark.asyncio
async def test_insert_file_not_found(mock_context, tmp_path, monkeypatch):
    """Test insert file not found error."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    result = await insert_markdown_section(
        mock_context,
        "plan.md",
        "## Section",
        "Content",
    )

    assert "Error" in result
    assert "not found" in result


@pytest.mark.asyncio
async def test_insert_no_headings(mock_context, tmp_path, monkeypatch):
    """Test insert error when file has no headings."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    (tmp_path / "plan.md").write_text("Just some text without headings")

    result = await insert_markdown_section(
        mock_context,
        "plan.md",
        "## Section",
        "Content",
    )

    assert "Error" in result
    assert "No headings found" in result


@pytest.mark.asyncio
async def test_insert_agent_scoping(mock_context, tmp_path, monkeypatch):
    """Test that insert respects agent scoping restrictions."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    (tmp_path / "research.md").write_text("# Research\n\n## Findings\n\nData")

    result = await insert_markdown_section(
        mock_context,
        "research.md",
        "## Findings",
        "New findings",
    )

    assert "Error" in result
    assert "Plan agent can only write to" in result


@pytest.mark.asyncio
async def test_insert_file_operation_tracking(mock_context, tmp_path, monkeypatch):
    """Test that insert file operations are tracked."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    (tmp_path / "plan.md").write_text("# Plan\n\n## Section\n\nContent")

    await insert_markdown_section(
        mock_context,
        "plan.md",
        "## Section",
        "New content",
    )

    assert len(mock_context.deps.file_tracker.operations) == 1


@pytest.mark.asyncio
async def test_insert_crlf_preserved(mock_context, tmp_path, monkeypatch):
    """Test that insert preserves CRLF line endings."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = "# Plan\r\n\r\n## Section\r\n\r\nExisting\r\n"
    (tmp_path / "plan.md").write_bytes(initial_content.encode("utf-8"))

    result = await insert_markdown_section(
        mock_context,
        "plan.md",
        "## Section",
        "New content",
    )

    assert "Successfully inserted" in result
    new_content = (tmp_path / "plan.md").read_bytes().decode("utf-8")
    assert "\r\n" in new_content


@pytest.mark.asyncio
async def test_insert_no_match_shows_available(mock_context, tmp_path, monkeypatch):
    """Test that insert with no match shows available headings."""
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

    result = await insert_markdown_section(
        mock_context,
        "plan.md",
        "## Nonexistent Section",
        "New content",
    )

    assert "No section matching" in result
    assert "plan.md" in result


# =============================================================================
# Varied content tests for both tools
# =============================================================================


@pytest.mark.asyncio
async def test_replace_with_code_block(mock_context, tmp_path, monkeypatch):
    """Test replacing section containing fenced code blocks."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Plan

## Implementation

Old code here

## Notes
"""
    (tmp_path / "plan.md").write_text(initial_content)

    new_code = """```python
def hello():
    print("Hello, world!")
```

```javascript
console.log("Also JS");
```"""

    result = await replace_markdown_section(
        mock_context,
        "plan.md",
        "## Implementation",
        new_code,
    )

    assert "Successfully replaced" in result
    new_content = (tmp_path / "plan.md").read_text()
    assert "```python" in new_content
    assert 'print("Hello, world!")' in new_content
    assert "```javascript" in new_content
    assert "## Notes" in new_content


@pytest.mark.asyncio
async def test_insert_with_code_block(mock_context, tmp_path, monkeypatch):
    """Test inserting content containing fenced code blocks."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Plan

## Implementation

Existing implementation

## Notes
"""
    (tmp_path / "plan.md").write_text(initial_content)

    new_code = """```python
def new_function():
    return 42
```"""

    result = await insert_markdown_section(
        mock_context,
        "plan.md",
        "## Implementation",
        new_code,
    )

    assert "Successfully inserted" in result
    new_content = (tmp_path / "plan.md").read_text()
    assert "Existing implementation" in new_content
    assert "```python" in new_content
    assert "return 42" in new_content


@pytest.mark.asyncio
async def test_replace_with_nested_bullet_list(mock_context, tmp_path, monkeypatch):
    """Test replacing section with nested bullet lists."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Plan

## Requirements

Old requirements

## Notes
"""
    (tmp_path / "plan.md").write_text(initial_content)

    nested_list = """- Parent item 1
  - Child item 1.1
  - Child item 1.2
    - Grandchild 1.2.1
- Parent item 2
  - Child item 2.1"""

    result = await replace_markdown_section(
        mock_context,
        "plan.md",
        "## Requirements",
        nested_list,
    )

    assert "Successfully replaced" in result
    new_content = (tmp_path / "plan.md").read_text()
    assert "- Parent item 1" in new_content
    assert "  - Child item 1.1" in new_content
    assert "    - Grandchild 1.2.1" in new_content


@pytest.mark.asyncio
async def test_replace_with_numbered_list(mock_context, tmp_path, monkeypatch):
    """Test replacing section with numbered lists."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Plan

## Steps

Old steps

## Notes
"""
    (tmp_path / "plan.md").write_text(initial_content)

    numbered_list = """1. First step
2. Second step
   1. Substep 2.1
   2. Substep 2.2
3. Third step"""

    result = await replace_markdown_section(
        mock_context,
        "plan.md",
        "## Steps",
        numbered_list,
    )

    assert "Successfully replaced" in result
    new_content = (tmp_path / "plan.md").read_text()
    assert "1. First step" in new_content
    assert "   1. Substep 2.1" in new_content


@pytest.mark.asyncio
async def test_replace_with_table(mock_context, tmp_path, monkeypatch):
    """Test replacing section with markdown tables."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Plan

## Data

Old data

## Notes
"""
    (tmp_path / "plan.md").write_text(initial_content)

    table = """| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Data A   | Data B   | Data C   |
| Data D   | Data E   | Data F   |"""

    result = await replace_markdown_section(
        mock_context,
        "plan.md",
        "## Data",
        table,
    )

    assert "Successfully replaced" in result
    new_content = (tmp_path / "plan.md").read_text()
    assert "| Column 1 |" in new_content
    assert "|----------|" in new_content
    assert "| Data A   |" in new_content


@pytest.mark.asyncio
async def test_replace_with_links_and_images(mock_context, tmp_path, monkeypatch):
    """Test replacing section with links and images."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Plan

## Resources

Old resources

## Notes
"""
    (tmp_path / "plan.md").write_text(initial_content)

    links_content = """Check out [this link](https://example.com) for more info.

![Alt text](./image.png "Image title")

Also see [reference link][ref].

[ref]: https://reference.com "Reference"
"""

    result = await replace_markdown_section(
        mock_context,
        "plan.md",
        "## Resources",
        links_content,
    )

    assert "Successfully replaced" in result
    new_content = (tmp_path / "plan.md").read_text()
    assert "[this link](https://example.com)" in new_content
    assert "![Alt text](./image.png" in new_content
    assert "[ref]: https://reference.com" in new_content


@pytest.mark.asyncio
async def test_replace_with_blockquote(mock_context, tmp_path, monkeypatch):
    """Test replacing section with blockquotes."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Plan

## Quotes

Old quote

## Notes
"""
    (tmp_path / "plan.md").write_text(initial_content)

    blockquote = """> This is a blockquote.
>
> It has multiple lines.
>
> > And nested quotes too.
"""

    result = await replace_markdown_section(
        mock_context,
        "plan.md",
        "## Quotes",
        blockquote,
    )

    assert "Successfully replaced" in result
    new_content = (tmp_path / "plan.md").read_text()
    assert "> This is a blockquote." in new_content
    assert "> > And nested quotes too." in new_content


@pytest.mark.asyncio
async def test_replace_with_horizontal_rule(mock_context, tmp_path, monkeypatch):
    """Test replacing section containing horizontal rules."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Plan

## Sections

Old content

## Notes
"""
    (tmp_path / "plan.md").write_text(initial_content)

    hr_content = """Part 1 content

---

Part 2 content

***

Part 3 content"""

    result = await replace_markdown_section(
        mock_context,
        "plan.md",
        "## Sections",
        hr_content,
    )

    assert "Successfully replaced" in result
    new_content = (tmp_path / "plan.md").read_text()
    assert "---" in new_content
    assert "***" in new_content
    assert "Part 1 content" in new_content


@pytest.mark.asyncio
async def test_replace_with_unicode(mock_context, tmp_path, monkeypatch):
    """Test replacing section with unicode content (emoji, CJK, etc.)."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Plan

## Content

Old content

## Notes
"""
    (tmp_path / "plan.md").write_text(initial_content)

    unicode_content = """🚀 Launch features:
- 日本語のテスト (Japanese test)
- 中文测试 (Chinese test)
- Émojis: 🎉 🔥 ✨ 💻
- Special: — « » • † ‡ © ® ™
- Math: α β γ δ ∑ ∏ √ ∞"""

    result = await replace_markdown_section(
        mock_context,
        "plan.md",
        "## Content",
        unicode_content,
    )

    assert "Successfully replaced" in result
    new_content = (tmp_path / "plan.md").read_text()
    assert "🚀" in new_content
    assert "日本語のテスト" in new_content
    assert "中文测试" in new_content
    assert "∞" in new_content


@pytest.mark.asyncio
async def test_replace_deeply_nested_headings(mock_context, tmp_path, monkeypatch):
    """Test replacing with deeply nested headings (h1 -> h6)."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Plan

## Top Section

Old content

## Another Section
"""
    (tmp_path / "plan.md").write_text(initial_content)

    nested_headings = """Level 2 intro

### Level 3

#### Level 4

##### Level 5

###### Level 6

Deepest content here."""

    result = await replace_markdown_section(
        mock_context,
        "plan.md",
        "## Top Section",
        nested_headings,
    )

    assert "Successfully replaced" in result
    new_content = (tmp_path / "plan.md").read_text()
    assert "### Level 3" in new_content
    assert "###### Level 6" in new_content
    assert "Deepest content here." in new_content
    assert "## Another Section" in new_content


@pytest.mark.asyncio
async def test_insert_with_table(mock_context, tmp_path, monkeypatch):
    """Test inserting content with tables."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Plan

## Data

Existing data

## Notes
"""
    (tmp_path / "plan.md").write_text(initial_content)

    table = """| New Col | Values |
|---------|--------|
| Row 1   | 100    |"""

    result = await insert_markdown_section(
        mock_context,
        "plan.md",
        "## Data",
        table,
    )

    assert "Successfully inserted" in result
    new_content = (tmp_path / "plan.md").read_text()
    assert "Existing data" in new_content
    assert "| New Col |" in new_content


@pytest.mark.asyncio
async def test_insert_with_unicode(mock_context, tmp_path, monkeypatch):
    """Test inserting unicode content."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Plan

## Features

Existing features

## Notes
"""
    (tmp_path / "plan.md").write_text(initial_content)

    result = await insert_markdown_section(
        mock_context,
        "plan.md",
        "## Features",
        "🎯 新機能: ダークモード",
    )

    assert "Successfully inserted" in result
    new_content = (tmp_path / "plan.md").read_text()
    assert "Existing features" in new_content
    assert "🎯" in new_content
    assert "新機能" in new_content


# =============================================================================
# Tests for section number parsing utilities
# =============================================================================


class TestParseSectionNumber:
    """Tests for parse_section_number utility."""

    def test_simple_number_with_trailing_dot(self):
        result = parse_section_number("## 3. Title")
        assert result is not None
        assert result.prefix == "3"
        assert result.has_trailing_dot is True

    def test_dotted_number_no_trailing_dot(self):
        result = parse_section_number("### 4.4 Title")
        assert result is not None
        assert result.prefix == "4.4"
        assert result.has_trailing_dot is False

    def test_dotted_number_with_trailing_dot(self):
        result = parse_section_number("### 4.4. Title")
        assert result is not None
        assert result.prefix == "4.4"
        assert result.has_trailing_dot is True

    def test_deep_nesting(self):
        result = parse_section_number("#### 1.2.3.4 Title")
        assert result is not None
        assert result.prefix == "1.2.3.4"
        assert result.has_trailing_dot is False

    def test_no_number(self):
        assert parse_section_number("## Title") is None

    def test_h1_with_number(self):
        result = parse_section_number("# 1. Introduction")
        assert result is not None
        assert result.prefix == "1"
        assert result.has_trailing_dot is True

    def test_h6_with_number(self):
        result = parse_section_number("###### 1.2.3.4.5.6 Deep")
        assert result is not None
        assert result.prefix == "1.2.3.4.5.6"

    def test_large_numbers(self):
        result = parse_section_number("## 10.20.30 Title")
        assert result is not None
        assert result.prefix == "10.20.30"


class TestIncrementSectionNumber:
    """Tests for increment_section_number utility."""

    def test_simple_increment(self):
        section = SectionNumber(prefix="3", has_trailing_dot=False)
        assert increment_section_number(section) == "4"

    def test_simple_increment_with_dot(self):
        section = SectionNumber(prefix="3", has_trailing_dot=True)
        assert increment_section_number(section) == "4."

    def test_dotted_increment(self):
        section = SectionNumber(prefix="4.4", has_trailing_dot=False)
        assert increment_section_number(section) == "4.5"

    def test_dotted_increment_with_trailing_dot(self):
        section = SectionNumber(prefix="4.4", has_trailing_dot=True)
        assert increment_section_number(section) == "4.5."

    def test_deep_nesting_increment(self):
        section = SectionNumber(prefix="1.2.3", has_trailing_dot=False)
        assert increment_section_number(section) == "1.2.4"


class TestDecrementSectionNumber:
    """Tests for decrement_section_number utility."""

    def test_simple_decrement(self):
        section = SectionNumber(prefix="4", has_trailing_dot=False)
        assert decrement_section_number(section) == "3"

    def test_simple_decrement_with_dot(self):
        section = SectionNumber(prefix="4", has_trailing_dot=True)
        assert decrement_section_number(section) == "3."

    def test_dotted_decrement(self):
        section = SectionNumber(prefix="4.5", has_trailing_dot=False)
        assert decrement_section_number(section) == "4.4"

    def test_deep_nesting_decrement(self):
        section = SectionNumber(prefix="1.2.4", has_trailing_dot=False)
        assert decrement_section_number(section) == "1.2.3"


class TestRenumberHeadingsAfter:
    """Tests for renumber_headings_after utility."""

    def test_increment_same_level(self):
        lines = [
            "# Doc",
            "## 1. First",
            "Content",
            "## 2. Second",
            "Content",
            "## 3. Third",
        ]
        result = renumber_headings_after(
            lines, start_line=3, heading_level=2, increment=True
        )
        assert result[3] == "## 3. Second"
        assert result[5] == "## 4. Third"
        # First section unchanged
        assert result[1] == "## 1. First"

    def test_decrement_same_level(self):
        lines = [
            "# Doc",
            "## 1. First",
            "## 3. Third",
            "## 4. Fourth",
        ]
        result = renumber_headings_after(
            lines, start_line=2, heading_level=2, increment=False
        )
        assert result[2] == "## 2. Third"
        assert result[3] == "## 3. Fourth"
        # First section unchanged
        assert result[1] == "## 1. First"

    def test_stops_at_higher_level(self):
        lines = [
            "# Doc",
            "## 4. Overview",
            "### 4.1 First",
            "### 4.2 Second",
            "## 5. Next Chapter",
            "### 5.1 Sub",
        ]
        # Increment ### level sections starting from line 3
        result = renumber_headings_after(
            lines, start_line=3, heading_level=3, increment=True
        )
        # 4.2 -> 4.3
        assert result[3] == "### 4.3 Second"
        # 5.1 should NOT be changed (different parent section)
        assert result[5] == "### 5.1 Sub"

    def test_skips_unnumbered_headings(self):
        lines = [
            "# Doc",
            "## 1. First",
            "## Unnumbered",
            "## 2. Second",
        ]
        result = renumber_headings_after(
            lines, start_line=2, heading_level=2, increment=True
        )
        # Unnumbered stays unnumbered
        assert result[2] == "## Unnumbered"
        # 2. -> 3.
        assert result[3] == "## 3. Second"

    def test_skips_different_levels(self):
        lines = [
            "### 4.1 Sub",
            "Content",
            "#### 4.1.1 Subsub",
            "### 4.2 Another Sub",
        ]
        # Increment ### level starting from line 3
        result = renumber_headings_after(
            lines, start_line=3, heading_level=3, increment=True
        )
        # #### line should be unchanged
        assert result[2] == "#### 4.1.1 Subsub"
        # ### line should be incremented
        assert result[3] == "### 4.3 Another Sub"


# =============================================================================
# Tests for insert_markdown_section auto-increment
# =============================================================================


@pytest.mark.asyncio
async def test_insert_increments_subsequent_numbered_sections(
    mock_context, tmp_path, monkeypatch
):
    """Test that inserting a numbered section increments following sections."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Doc

## 4. Overview

Content

### 4.1 First

Content

### 4.2 Second

Content

### 4.3 Third

Content

## 5. Next Chapter
"""
    (tmp_path / "plan.md").write_text(initial_content)

    # Insert new "### 4.2 New Section" after "### 4.1 First"
    result = await insert_markdown_section(
        mock_context,
        "plan.md",
        "### 4.1 First",
        "New content here",
        new_heading="### 4.2 New Section",
    )

    assert "Successfully inserted" in result

    new_content = (tmp_path / "plan.md").read_text()
    # New section is at 4.2
    assert "### 4.2 New Section" in new_content
    # Old 4.2 -> 4.3
    assert "### 4.3 Second" in new_content
    # Old 4.3 -> 4.4
    assert "### 4.4 Third" in new_content
    # ## 5 should not be changed (different level)
    assert "## 5. Next Chapter" in new_content


@pytest.mark.asyncio
async def test_insert_does_not_increment_unnumbered_sections(
    mock_context, tmp_path, monkeypatch
):
    """Test that inserting a numbered section does not affect unnumbered sections."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Doc

## Overview

### 4.1 First

Content

### Unnumbered Section

Content

### 4.2 Second

Content
"""
    (tmp_path / "plan.md").write_text(initial_content)

    result = await insert_markdown_section(
        mock_context,
        "plan.md",
        "### 4.1 First",
        "New content",
        new_heading="### 4.2 New",
    )

    assert "Successfully inserted" in result

    new_content = (tmp_path / "plan.md").read_text()
    # Unnumbered section stays unchanged
    assert "### Unnumbered Section" in new_content
    # Old 4.2 -> 4.3
    assert "### 4.3 Second" in new_content


@pytest.mark.asyncio
async def test_insert_without_numbered_heading_does_not_renumber(
    mock_context, tmp_path, monkeypatch
):
    """Test that inserting without a numbered heading does not trigger renumbering."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Doc

## 4. Overview

### 4.1 First

Content

### 4.2 Second

Content
"""
    (tmp_path / "plan.md").write_text(initial_content)

    # Insert with unnumbered heading
    result = await insert_markdown_section(
        mock_context,
        "plan.md",
        "### 4.1 First",
        "New content",
        new_heading="### Notes",
    )

    assert "Successfully inserted" in result

    new_content = (tmp_path / "plan.md").read_text()
    # 4.2 should stay 4.2 (unnumbered heading was inserted)
    assert "### 4.2 Second" in new_content


# =============================================================================
# Tests for remove_markdown_section
# =============================================================================


@pytest.mark.asyncio
async def test_basic_remove(mock_context, tmp_path, monkeypatch):
    """Test basic section removal."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Plan

## Requirements

- Req 1
- Req 2

## Technical Notes

Some technical details
"""
    (tmp_path / "plan.md").write_text(initial_content)

    result = await remove_markdown_section(
        mock_context,
        "plan.md",
        "## Requirements",
    )

    assert "Successfully removed" in result
    assert "## Requirements" in result

    new_content = (tmp_path / "plan.md").read_text()
    # Requirements section removed
    assert "## Requirements" not in new_content
    assert "- Req 1" not in new_content
    # Other sections preserved
    assert "## Technical Notes" in new_content
    assert "Some technical details" in new_content


@pytest.mark.asyncio
async def test_remove_decrements_numbered_sections(mock_context, tmp_path, monkeypatch):
    """Test that removing a numbered section decrements following sections."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Doc

### 4.1 First

Content

### 4.2 Second

Content

### 4.3 Third

Content
"""
    (tmp_path / "plan.md").write_text(initial_content)

    result = await remove_markdown_section(
        mock_context,
        "plan.md",
        "### 4.2 Second",
    )

    assert "Successfully removed" in result

    new_content = (tmp_path / "plan.md").read_text()
    # 4.1 stays 4.1
    assert "### 4.1 First" in new_content
    # 4.2 is removed
    assert "### 4.2 Second" not in new_content
    # 4.3 -> 4.2
    assert "### 4.2 Third" in new_content


@pytest.mark.asyncio
async def test_remove_fuzzy_matching(mock_context, tmp_path, monkeypatch):
    """Test that remove uses fuzzy matching."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Plan

## Requirements

Content
"""
    (tmp_path / "plan.md").write_text(initial_content)

    # Use typo
    result = await remove_markdown_section(
        mock_context,
        "plan.md",
        "## Requirments",  # typo
    )

    assert "Successfully removed" in result
    assert "%" in result  # confidence shown

    new_content = (tmp_path / "plan.md").read_text()
    assert "## Requirements" not in new_content


@pytest.mark.asyncio
async def test_remove_at_eof(mock_context, tmp_path, monkeypatch):
    """Test removing section at end of file."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Plan

## First Section

Content

## Last Section

Last content
"""
    (tmp_path / "plan.md").write_text(initial_content)

    result = await remove_markdown_section(
        mock_context,
        "plan.md",
        "## Last Section",
    )

    assert "Successfully removed" in result

    new_content = (tmp_path / "plan.md").read_text()
    assert "## Last Section" not in new_content
    assert "Last content" not in new_content
    assert "## First Section" in new_content


@pytest.mark.asyncio
async def test_remove_with_subsections(mock_context, tmp_path, monkeypatch):
    """Test that removing a section removes its subsections too."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Plan

## Parent Section

Intro

### Child Section 1

Child content

### Child Section 2

More child content

## Next Section

Other content
"""
    (tmp_path / "plan.md").write_text(initial_content)

    result = await remove_markdown_section(
        mock_context,
        "plan.md",
        "## Parent Section",
    )

    assert "Successfully removed" in result

    new_content = (tmp_path / "plan.md").read_text()
    assert "## Parent Section" not in new_content
    assert "### Child Section" not in new_content
    assert "## Next Section" in new_content


@pytest.mark.asyncio
async def test_remove_file_not_found(mock_context, tmp_path, monkeypatch):
    """Test remove file not found error."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    result = await remove_markdown_section(
        mock_context,
        "plan.md",
        "## Section",
    )

    assert "Error" in result
    assert "not found" in result


@pytest.mark.asyncio
async def test_remove_no_headings(mock_context, tmp_path, monkeypatch):
    """Test remove error when file has no headings."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    (tmp_path / "plan.md").write_text("Just some text without headings")

    result = await remove_markdown_section(
        mock_context,
        "plan.md",
        "## Section",
    )

    assert "Error" in result
    assert "No headings found" in result


@pytest.mark.asyncio
async def test_remove_no_match(mock_context, tmp_path, monkeypatch):
    """Test remove with no matching section."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Plan

## Requirements

Content
"""
    (tmp_path / "plan.md").write_text(initial_content)

    result = await remove_markdown_section(
        mock_context,
        "plan.md",
        "## Nonexistent",
    )

    assert "No section matching" in result


@pytest.mark.asyncio
async def test_remove_agent_scoping(mock_context, tmp_path, monkeypatch):
    """Test that remove respects agent scoping restrictions."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    (tmp_path / "research.md").write_text("# Research\n\n## Findings\n\nData")

    result = await remove_markdown_section(
        mock_context,
        "research.md",
        "## Findings",
    )

    assert "Error" in result
    assert "Plan agent can only write to" in result


@pytest.mark.asyncio
async def test_remove_file_operation_tracking(mock_context, tmp_path, monkeypatch):
    """Test that remove file operations are tracked."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    (tmp_path / "plan.md").write_text("# Plan\n\n## Section\n\nContent")

    await remove_markdown_section(
        mock_context,
        "plan.md",
        "## Section",
    )

    assert len(mock_context.deps.file_tracker.operations) == 1


@pytest.mark.asyncio
async def test_remove_crlf_preserved(mock_context, tmp_path, monkeypatch):
    """Test that remove preserves CRLF line endings."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = (
        "# Plan\r\n\r\n## Section\r\n\r\nContent\r\n\r\n## Other\r\n\r\nMore\r\n"
    )
    (tmp_path / "plan.md").write_bytes(initial_content.encode("utf-8"))

    result = await remove_markdown_section(
        mock_context,
        "plan.md",
        "## Section",
    )

    assert "Successfully removed" in result
    new_content = (tmp_path / "plan.md").read_bytes().decode("utf-8")
    assert "\r\n" in new_content


@pytest.mark.asyncio
async def test_remove_unnumbered_does_not_affect_others(
    mock_context, tmp_path, monkeypatch
):
    """Test that removing an unnumbered section does not trigger renumbering."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Doc

### 4.1 First

Content

### Notes

Content

### 4.2 Second

Content
"""
    (tmp_path / "plan.md").write_text(initial_content)

    result = await remove_markdown_section(
        mock_context,
        "plan.md",
        "### Notes",
    )

    assert "Successfully removed" in result

    new_content = (tmp_path / "plan.md").read_text()
    # Numbered sections unchanged (Notes was unnumbered)
    assert "### 4.1 First" in new_content
    assert "### 4.2 Second" in new_content


@pytest.mark.asyncio
async def test_sequential_replace_operations_no_corruption(
    tmp_path, mock_context, monkeypatch
):
    """Test that multiple sequential replace operations don't corrupt the file.

    This tests the fix for a bug where write_markdown_file didn't add a trailing
    newline, causing subsequent operations to corrupt content.
    """
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Document

## Section 1

First section content.

## Section 2

Second section content with `.jpeg` extension reference.

## Section 3

Third section content.
"""
    (tmp_path / "plan.md").write_text(initial_content)

    # First replace operation
    result1 = await replace_markdown_section(
        mock_context,
        "plan.md",
        "## Section 1",
        "Updated first section.",
    )
    assert "Successfully replaced" in result1

    # Second replace operation (should not corrupt Section 2)
    result2 = await replace_markdown_section(
        mock_context,
        "plan.md",
        "## Section 2",
        "Updated second section with `.jpeg` extension.",
    )
    assert "Successfully replaced" in result2

    # Read final content and verify no corruption
    final_content = (tmp_path / "plan.md").read_text()

    # Section 1 should be updated
    assert "Updated first section." in final_content
    # Section 2 should be updated and not corrupted
    assert "Updated second section with `.jpeg` extension." in final_content
    # .jpeg should NOT be split across lines
    assert ".jp\neg" not in final_content
    # Section 3 should be intact
    assert "## Section 3" in final_content
    assert "Third section content." in final_content


@pytest.mark.asyncio
async def test_written_files_end_with_newline(tmp_path, mock_context, monkeypatch):
    """Verify that files written by markdown tools end with a newline."""
    mock_context.deps.agent_mode = AgentType.PLAN
    monkeypatch.setattr(
        "shotgun.agents.tools.file_management.get_shotgun_base_path", lambda: tmp_path
    )

    initial_content = """# Document

## Section 1

Content here.
"""
    (tmp_path / "plan.md").write_text(initial_content)

    await replace_markdown_section(
        mock_context,
        "plan.md",
        "## Section 1",
        "New content.",
    )

    final_content = (tmp_path / "plan.md").read_text()
    assert final_content.endswith("\n"), "File should end with a newline"
