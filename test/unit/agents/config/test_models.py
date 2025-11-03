"""Tests for agents.config.models module."""

import pytest

from shotgun.agents.config.models import ModelName, get_model_short_name


def test_get_model_short_name_claude_sonnet():
    """Test get_model_short_name for Claude Sonnet 4.5."""
    result = get_model_short_name(ModelName.CLAUDE_SONNET_4_5)
    assert result == "Sonnet 4.5"


def test_get_model_short_name_claude_opus():
    """Test get_model_short_name for Claude Opus 4.1."""
    result = get_model_short_name(ModelName.CLAUDE_OPUS_4_1)
    assert result == "Opus 4.1"


def test_get_model_short_name_claude_haiku():
    """Test get_model_short_name for Claude Haiku 4.5."""
    result = get_model_short_name(ModelName.CLAUDE_HAIKU_4_5)
    assert result == "Haiku 4.5"


def test_get_model_short_name_gpt_5():
    """Test get_model_short_name for GPT-5."""
    result = get_model_short_name(ModelName.GPT_5)
    assert result == "GPT-5"


def test_get_model_short_name_gpt_5_mini():
    """Test get_model_short_name for GPT-5 Mini."""
    result = get_model_short_name(ModelName.GPT_5_MINI)
    assert result == "GPT-5 Mini"


def test_get_model_short_name_gemini_pro():
    """Test get_model_short_name for Gemini 2.5 Pro."""
    result = get_model_short_name(ModelName.GEMINI_2_5_PRO)
    assert result == "Gemini 2.5 Pro"


def test_get_model_short_name_gemini_flash():
    """Test get_model_short_name for Gemini 2.5 Flash."""
    result = get_model_short_name(ModelName.GEMINI_2_5_FLASH)
    assert result == "Gemini 2.5 Flash"


def test_get_model_short_name_all_models_have_mapping():
    """Test that all ModelName enum values have a short name mapping."""
    for model_name in ModelName:
        short_name = get_model_short_name(model_name)
        # Should not return the enum string representation
        assert short_name != str(model_name)
        # Should return a non-empty string
        assert len(short_name) > 0
