"""Tests for agents.config.models module."""

from shotgun.agents.config.models import MODEL_SPECS, ModelName


def test_model_spec_short_name_claude_sonnet():
    """Test ModelSpec short_name for Claude Sonnet 4.5."""
    spec = MODEL_SPECS[ModelName.CLAUDE_SONNET_4_5]
    assert spec.short_name == "Sonnet 4.5"


def test_model_spec_short_name_claude_opus():
    """Test ModelSpec short_name for Claude Opus 4.5."""
    spec = MODEL_SPECS[ModelName.CLAUDE_OPUS_4_5]
    assert spec.short_name == "Opus 4.5"


def test_model_spec_short_name_claude_haiku():
    """Test ModelSpec short_name for Claude Haiku 4.5."""
    spec = MODEL_SPECS[ModelName.CLAUDE_HAIKU_4_5]
    assert spec.short_name == "Haiku 4.5"


def test_model_spec_short_name_gpt_5_1():
    """Test ModelSpec short_name for GPT-5.1."""
    spec = MODEL_SPECS[ModelName.GPT_5_1]
    assert spec.short_name == "GPT-5.1"


def test_model_spec_short_name_gpt_5_2():
    """Test ModelSpec short_name for GPT-5.2."""
    spec = MODEL_SPECS[ModelName.GPT_5_2]
    assert spec.short_name == "GPT-5.2"


def test_model_spec_short_name_gemini_pro():
    """Test ModelSpec short_name for Gemini 2.5 Pro."""
    spec = MODEL_SPECS[ModelName.GEMINI_2_5_PRO]
    assert spec.short_name == "Gemini 2.5 Pro"


def test_model_spec_short_name_gemini_flash():
    """Test ModelSpec short_name for Gemini 2.5 Flash."""
    spec = MODEL_SPECS[ModelName.GEMINI_2_5_FLASH]
    assert spec.short_name == "Gemini 2.5 Flash"


def test_all_models_have_short_name():
    """Test that all ModelName enum values have a short_name in MODEL_SPECS."""
    for model_name in ModelName:
        spec = MODEL_SPECS[model_name]
        # Should have a short_name field
        assert hasattr(spec, "short_name")
        # Should not return the enum string representation
        assert spec.short_name != str(model_name)
        # Should return a non-empty string
        assert len(spec.short_name) > 0
