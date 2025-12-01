"""Tests for CLI spec models."""

from datetime import datetime, timezone

from shotgun.cli.spec.models import SpecMeta


def test_spec_meta_creation() -> None:
    """Test SpecMeta model creation."""
    now = datetime.now(timezone.utc)
    meta = SpecMeta(
        version_id="version-123",
        spec_id="spec-456",
        spec_name="My Test Spec",
        workspace_id="workspace-789",
        is_latest=True,
        pulled_at=now,
    )

    assert meta.version_id == "version-123"
    assert meta.spec_id == "spec-456"
    assert meta.spec_name == "My Test Spec"
    assert meta.workspace_id == "workspace-789"
    assert meta.is_latest is True
    assert meta.pulled_at == now


def test_spec_meta_serialization() -> None:
    """Test SpecMeta model serialization to JSON."""
    now = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
    meta = SpecMeta(
        version_id="version-123",
        spec_id="spec-456",
        spec_name="My Test Spec",
        workspace_id="workspace-789",
        is_latest=False,
        pulled_at=now,
    )

    json_str = meta.model_dump_json(indent=2)
    assert '"version_id": "version-123"' in json_str
    assert '"spec_name": "My Test Spec"' in json_str
    assert '"is_latest": false' in json_str


def test_spec_meta_from_json() -> None:
    """Test SpecMeta model deserialization from JSON."""
    json_str = """{
        "version_id": "v-id",
        "spec_id": "s-id",
        "spec_name": "Test",
        "workspace_id": "w-id",
        "is_latest": true,
        "pulled_at": "2024-01-15T10:30:00Z"
    }"""

    meta = SpecMeta.model_validate_json(json_str)
    assert meta.version_id == "v-id"
    assert meta.spec_name == "Test"
    assert meta.is_latest is True
