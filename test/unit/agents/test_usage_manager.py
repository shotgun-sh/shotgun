"""Tests for SessionUsageManager usage aggregation, formatting, and persistence."""

from pathlib import Path

import pytest
from pydantic_ai import RunUsage

from shotgun.agents.config.models import ProviderType
from shotgun.agents.usage_manager import (
    SessionUsageManager,
    UsageSummaryEntry,
    format_usage_hint,
)


@pytest.fixture()
def usage_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(
        "shotgun.agents.usage_manager.get_shotgun_home", lambda: tmp_path
    )
    return tmp_path


def test_usage_breakdown_aggregates_by_model(usage_home: Path) -> None:
    manager = SessionUsageManager()
    manager.add_usage(
        RunUsage(input_tokens=10, output_tokens=5, cache_read_tokens=2),
        model_name="gpt-4o-mini",
        provider=ProviderType.OPENAI,
    )
    manager.add_usage(
        RunUsage(input_tokens=2, output_tokens=1, cache_read_tokens=1),
        model_name="gpt-4o-mini",
        provider=ProviderType.OPENAI,
    )
    manager.add_usage(
        RunUsage(input_tokens=7, output_tokens=3, cache_read_tokens=0),
        model_name="claude-3.5-sonnet",
        provider=ProviderType.ANTHROPIC,
    )

    breakdown = manager.get_usage_breakdown()

    assert len(breakdown) == 2
    # Sorted alphabetically by model name
    assert breakdown[0].model_name == "claude-3.5-sonnet"
    assert breakdown[1].model_name == "gpt-4o-mini"
    # Aggregated totals for gpt-4o-mini
    gpt_usage = breakdown[1].usage
    assert gpt_usage.input_tokens == 12
    assert gpt_usage.output_tokens == 6
    assert gpt_usage.cache_read_tokens == 3
    assert (usage_home / "usage.json").exists()


def test_build_usage_hint_renders_markdown_sections(usage_home: Path) -> None:
    manager = SessionUsageManager()
    manager.add_usage(
        RunUsage(input_tokens=4, output_tokens=6, cache_read_tokens=1),
        model_name="claude-3.5-sonnet",
        provider=ProviderType.ANTHROPIC,
    )
    message = manager.build_usage_hint()

    assert message is not None
    assert message.startswith("# Token usage by model")
    assert "### claude-3.5-sonnet" in message
    assert "Input: 4" in message
    assert "Output: 6" in message


def test_format_usage_hint_handles_empty_breakdown() -> None:
    assert format_usage_hint([]) is None

    breakdown = [
        UsageSummaryEntry(
            model_name="gpt-4o",
            provider=ProviderType.OPENAI,
            usage=RunUsage(input_tokens=1, output_tokens=2, cache_read_tokens=0),
        )
    ]
    hint = format_usage_hint(breakdown)
    assert hint is not None
    assert "### gpt-4o" in hint
    assert "Input: 1" in hint


def test_persist_and_restore_usage_state(usage_home: Path) -> None:
    first_manager = SessionUsageManager()
    first_manager.add_usage(
        RunUsage(input_tokens=8, output_tokens=2, cache_read_tokens=0),
        model_name="gpt-4.1-mini",
        provider=ProviderType.OPENAI,
    )
    persisted_path = usage_home / "usage.json"
    assert persisted_path.exists()

    restored_manager = SessionUsageManager()
    report = restored_manager.get_usage_report()

    assert "gpt-4.1-mini" in report
    restored_usage = report["gpt-4.1-mini"]
    assert restored_usage.input_tokens == 8
    assert restored_usage.output_tokens == 2
