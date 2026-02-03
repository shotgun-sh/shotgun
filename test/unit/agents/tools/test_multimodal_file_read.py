"""Tests for multimodal_file_read tool capability checks."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic_ai import RunContext

from shotgun.agents.config.models import KeyProvider, ModelConfig, ProviderType
from shotgun.agents.models import AgentDeps
from shotgun.agents.tools.file_read_tools.multimodal_file_read import (
    multimodal_file_read,
)


def create_mock_deps(
    supports_pdf: bool = True, supports_images: bool = True
) -> AgentDeps:
    """Create mock AgentDeps with specified capabilities."""
    model_config = ModelConfig(
        name="test-model",
        provider=ProviderType.OPENAI_COMPATIBLE,
        key_provider=KeyProvider.BYOK,
        max_input_tokens=128_000,
        max_output_tokens=16_000,
        api_key="test",
        supports_pdf=supports_pdf,
        supports_images=supports_images,
    )

    # Create a minimal mock deps
    deps = MagicMock(spec=AgentDeps)
    deps.llm_model = model_config
    return deps


def create_mock_context(deps: AgentDeps) -> RunContext[AgentDeps]:
    """Create a mock RunContext with given deps."""
    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps
    return ctx


@pytest.mark.asyncio
async def test_pdf_not_supported_returns_error():
    """Test that PDF files are rejected when model doesn't support them."""
    deps = create_mock_deps(supports_pdf=False, supports_images=True)
    ctx = create_mock_context(deps)

    result = await multimodal_file_read(ctx, "test.pdf")

    assert "PDF files are not supported" in result.return_value
    assert "test-model" in result.return_value


@pytest.mark.asyncio
async def test_image_not_supported_returns_error_png():
    """Test that PNG files are rejected when model doesn't support images."""
    deps = create_mock_deps(supports_pdf=True, supports_images=False)
    ctx = create_mock_context(deps)

    result = await multimodal_file_read(ctx, "test.png")

    assert "Image files are not supported" in result.return_value
    assert "test-model" in result.return_value


@pytest.mark.asyncio
async def test_image_not_supported_returns_error_jpg():
    """Test that JPG files are rejected when model doesn't support images."""
    deps = create_mock_deps(supports_pdf=True, supports_images=False)
    ctx = create_mock_context(deps)

    result = await multimodal_file_read(ctx, "test.jpg")

    assert "Image files are not supported" in result.return_value


@pytest.mark.asyncio
async def test_image_not_supported_returns_error_jpeg():
    """Test that JPEG files are rejected when model doesn't support images."""
    deps = create_mock_deps(supports_pdf=True, supports_images=False)
    ctx = create_mock_context(deps)

    result = await multimodal_file_read(ctx, "test.jpeg")

    assert "Image files are not supported" in result.return_value


@pytest.mark.asyncio
async def test_image_not_supported_returns_error_gif():
    """Test that GIF files are rejected when model doesn't support images."""
    deps = create_mock_deps(supports_pdf=True, supports_images=False)
    ctx = create_mock_context(deps)

    result = await multimodal_file_read(ctx, "test.gif")

    assert "Image files are not supported" in result.return_value


@pytest.mark.asyncio
async def test_image_not_supported_returns_error_webp():
    """Test that WebP files are rejected when model doesn't support images."""
    deps = create_mock_deps(supports_pdf=True, supports_images=False)
    ctx = create_mock_context(deps)

    result = await multimodal_file_read(ctx, "test.webp")

    assert "Image files are not supported" in result.return_value


@pytest.mark.asyncio
async def test_both_unsupported():
    """Test error message when neither PDF nor images are supported."""
    deps = create_mock_deps(supports_pdf=False, supports_images=False)
    ctx = create_mock_context(deps)

    # PDF should fail
    pdf_result = await multimodal_file_read(ctx, "test.pdf")
    assert "PDF files are not supported" in pdf_result.return_value

    # Image should fail
    png_result = await multimodal_file_read(ctx, "test.png")
    assert "Image files are not supported" in png_result.return_value


@pytest.mark.asyncio
async def test_pdf_supported_proceeds_to_file_check(tmp_path: Path):
    """Test that PDF check passes when supported, then proceeds to file existence check."""
    deps = create_mock_deps(supports_pdf=True, supports_images=True)
    ctx = create_mock_context(deps)

    # Non-existent file should fail at file existence check, not capability check
    result = await multimodal_file_read(ctx, "/nonexistent/path/test.pdf")

    # Should get file not found error, not capability error
    assert "not found" in result.return_value.lower() or "Error" in result.return_value
    assert "PDF files are not supported" not in result.return_value


@pytest.mark.asyncio
async def test_image_supported_proceeds_to_file_check(tmp_path: Path):
    """Test that image check passes when supported, then proceeds to file existence check."""
    deps = create_mock_deps(supports_pdf=True, supports_images=True)
    ctx = create_mock_context(deps)

    # Non-existent file should fail at file existence check, not capability check
    result = await multimodal_file_read(ctx, "/nonexistent/path/test.png")

    # Should get file not found error, not capability error
    assert "not found" in result.return_value.lower() or "Error" in result.return_value
    assert "Image files are not supported" not in result.return_value
