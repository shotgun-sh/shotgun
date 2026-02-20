"""Tests for sub-agent model mapping."""

from shotgun.agents.config.models import (
    MODEL_SPECS,
    SUB_AGENT_MODEL_MAPPINGS,
    ModelName,
    get_sub_agent_model,
)


def test_anthropic_opus_maps_to_haiku():
    """Claude Opus 4.6 should map to Claude Haiku 4.5 for sub-agents."""
    assert get_sub_agent_model(ModelName.CLAUDE_OPUS_4_6) == ModelName.CLAUDE_HAIKU_4_5


def test_anthropic_sonnet_maps_to_haiku():
    """Claude Sonnet 4.6 should map to Claude Haiku 4.5 for sub-agents."""
    assert (
        get_sub_agent_model(ModelName.CLAUDE_SONNET_4_6) == ModelName.CLAUDE_HAIKU_4_5
    )


def test_anthropic_haiku_returns_self():
    """Claude Haiku 4.5 should return itself (already cheapest)."""
    assert get_sub_agent_model(ModelName.CLAUDE_HAIKU_4_5) == ModelName.CLAUDE_HAIKU_4_5


def test_gemini_pro_maps_to_flash():
    """Gemini 3.1 Pro should map to Gemini 3 Flash for sub-agents."""
    assert (
        get_sub_agent_model(ModelName.GEMINI_3_1_PRO_PREVIEW)
        == ModelName.GEMINI_3_FLASH_PREVIEW
    )


def test_gemini_flash_returns_self():
    """Gemini 3 Flash should return itself (already cheapest)."""
    assert (
        get_sub_agent_model(ModelName.GEMINI_3_FLASH_PREVIEW)
        == ModelName.GEMINI_3_FLASH_PREVIEW
    )


def test_gemini_flash_lite_returns_self():
    """Gemini 2.5 Flash Lite should return itself (already cheapest)."""
    assert (
        get_sub_agent_model(ModelName.GEMINI_2_5_FLASH_LITE)
        == ModelName.GEMINI_2_5_FLASH_LITE
    )


def test_openai_gpt51_returns_self():
    """GPT-5.1 should return itself (already cheapest)."""
    assert get_sub_agent_model(ModelName.GPT_5_1) == ModelName.GPT_5_1


def test_openai_gpt52_maps_to_gpt51():
    """GPT-5.2 should map to GPT-5.1 for sub-agents."""
    assert get_sub_agent_model(ModelName.GPT_5_2) == ModelName.GPT_5_1


def test_all_mappings_preserve_provider():
    """Ensure sub-agent models are from the same provider."""
    for main_model, sub_model in SUB_AGENT_MODEL_MAPPINGS.items():
        main_spec = MODEL_SPECS[main_model]
        sub_spec = MODEL_SPECS[sub_model]
        assert main_spec.provider == sub_spec.provider, (
            f"Model {main_model.value} maps to {sub_model.value} "
            f"but providers differ: {main_spec.provider} vs {sub_spec.provider}"
        )


def test_all_mapped_models_exist_in_specs():
    """Ensure all models in the mapping exist in MODEL_SPECS."""
    for main_model, sub_model in SUB_AGENT_MODEL_MAPPINGS.items():
        assert main_model in MODEL_SPECS, (
            f"Main model {main_model.value} not in MODEL_SPECS"
        )
        assert sub_model in MODEL_SPECS, (
            f"Sub model {sub_model.value} not in MODEL_SPECS"
        )


def test_unmapped_models_return_self():
    """Ensure models not in the mapping return themselves."""
    # Get all models that are NOT in the mapping keys
    unmapped_models = [m for m in ModelName if m not in SUB_AGENT_MODEL_MAPPINGS]

    for model in unmapped_models:
        assert get_sub_agent_model(model) == model, (
            f"Unmapped model {model.value} should return itself"
        )
