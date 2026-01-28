"""Unit tests for HintMessage model and widget."""

from shotgun.tui.screens.chat_screen.hint_message import HintMessage, HintMessageWidget


def test_hint_message_basic():
    """Test basic HintMessage creation."""
    hint = HintMessage(message="Test message")
    assert hint.message == "Test message"
    assert hint.kind == "hint"
    assert hint.email is None
    assert hint.markdown_after is None
    assert hint.link is None
    assert hint.link_text is None


def test_hint_message_with_email():
    """Test HintMessage with email field."""
    hint = HintMessage(
        message="Contact us for help",
        email="support@example.com",
        markdown_after="We'll get back to you soon.",
    )
    assert hint.message == "Contact us for help"
    assert hint.email == "support@example.com"
    assert hint.markdown_after == "We'll get back to you soon."


def test_hint_message_with_link():
    """Test HintMessage with link fields."""
    hint = HintMessage(
        message="Check out the docs",
        link="https://example.com/docs",
        link_text="Link to Documentation",
    )
    assert hint.message == "Check out the docs"
    assert hint.link == "https://example.com/docs"
    assert hint.link_text == "Link to Documentation"


def test_hint_message_with_all_fields():
    """Test HintMessage with all optional fields populated."""
    hint = HintMessage(
        message="Full featured message",
        email="test@example.com",
        markdown_after="Extra markdown content",
        link="https://example.com",
        link_text="Visit Website",
    )
    assert hint.message == "Full featured message"
    assert hint.email == "test@example.com"
    assert hint.markdown_after == "Extra markdown content"
    assert hint.link == "https://example.com"
    assert hint.link_text == "Visit Website"


def test_hint_message_serialization():
    """Test HintMessage JSON serialization."""
    hint = HintMessage(
        message="Test",
        link="https://example.com",
        link_text="Example Link",
    )

    # Serialize to dict
    data = hint.model_dump()
    assert data["message"] == "Test"
    assert data["kind"] == "hint"
    assert data["link"] == "https://example.com"
    assert data["link_text"] == "Example Link"

    # Deserialize back
    hint2 = HintMessage.model_validate(data)
    assert hint2.message == "Test"
    assert hint2.link == "https://example.com"
    assert hint2.link_text == "Example Link"


def test_hint_message_widget_initialization():
    """Test HintMessageWidget can be initialized."""
    hint = HintMessage(message="Test message")
    widget = HintMessageWidget(hint)
    assert widget.message == hint


def test_hint_message_widget_with_link():
    """Test HintMessageWidget with link fields."""
    hint = HintMessage(
        message="Check our guide",
        link="https://app.shotgun.sh/how-to-use",
        link_text="Link to Getting started guide",
    )
    widget = HintMessageWidget(hint)
    assert widget.message.link == "https://app.shotgun.sh/how-to-use"
    assert widget.message.link_text == "Link to Getting started guide"
