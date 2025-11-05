"""Onboarding popup modal for first-time users."""

import webbrowser

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Markdown, Static


class OnboardingModal(ModalScreen[None]):
    """Multi-page onboarding modal for new users.

    This modal presents helpful resources and tips for using Shotgun across
    multiple pages. Users can navigate between pages using Next/Back buttons.
    """

    CSS = """
        OnboardingModal {
            align: center middle;
        }

        #onboarding-container {
            width: 95;
            max-width: 100;
            height: auto;
            max-height: 90%;
            border: thick $primary;
            background: $surface;
            padding: 2;
        }

        #progress-sidebar {
            width: 26;
            dock: left;
            border-right: solid $primary;
            padding: 1;
            height: 100%;
        }

        #main-content {
            width: 1fr;
            height: auto;
        }

        #progress-header {
            text-style: bold;
            padding-bottom: 1;
            color: $text-accent;
        }

        .progress-item {
            padding: 1 0;
        }

        .progress-item-current {
            color: $accent;
            text-style: bold;
        }

        .progress-item-visited {
            color: $success;
        }

        .progress-item-unvisited {
            color: $text-muted;
        }

        #onboarding-header {
            text-style: bold;
            color: $text-accent;
            padding-bottom: 1;
            text-align: center;
        }

        #onboarding-content {
            height: 1fr;
            padding: 1 0;
        }

        #page-indicator {
            text-align: center;
            color: $text-muted;
            padding: 1 0;
        }

        #buttons-container {
            height: auto;
            padding: 1 0 0 0;
        }

        #navigation-buttons {
            width: 100%;
            height: auto;
            align: center middle;
        }

        .nav-button {
            margin: 0 1;
            min-width: 12;
        }

        #resource-sections {
            padding: 1 0;
            height: auto;
        }

        #resource-sections Button {
            width: 100%;
            margin: 0 0 2 0;
        }

        #video-section {
            padding: 0;
            margin: 0 0 1 0;
        }

        #docs-section {
            padding: 0;
            margin: 2 0 1 0;
        }
    """

    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("ctrl+c", "app.quit", "Quit"),
    ]

    def __init__(self) -> None:
        """Initialize the onboarding modal."""
        super().__init__()
        self.current_page = 0
        self.total_pages = 4
        self.page_titles = [
            "Getting Started",
            "Discovering the 5 Modes",
            "Prompting Better",
            "Context Management!",
        ]
        # Track which pages have been visited (in memory only)
        self.visited_pages: set[int] = {0}  # Start on page 0, so it's visited

    def compose(self) -> ComposeResult:
        """Compose the onboarding modal."""
        with Container(id="onboarding-container"):
            # Left sidebar for progress tracking
            with Container(id="progress-sidebar"):
                yield Static("Progress", id="progress-header")
                for i in range(self.total_pages):
                    yield Static(
                        f"{i + 1}. {self.page_titles[i]}",
                        id=f"progress-item-{i}",
                        classes="progress-item",
                    )

            # Main content area
            with Container(id="main-content"):
                yield Static("Welcome to Shotgun!", id="onboarding-header")
                with VerticalScroll(id="onboarding-content"):
                    yield Markdown(id="page-content")
                    # Resource sections (only shown on page 1)
                    with Container(id="resource-sections"):
                        yield Markdown(
                            "### 🎥 Video Demo\nWatch our demo video to see Shotgun in action",
                            id="video-section",
                        )
                        yield Button(
                            "▶️  Watch Demo Video",
                            id="youtube-button",
                            variant="success",
                        )
                        yield Markdown(
                            "### 📖 Documentation\nRead the comprehensive usage guide for detailed instructions",
                            id="docs-section",
                        )
                        yield Button(
                            "📚 Read Usage Guide", id="usage-button", variant="primary"
                        )
                yield Static(id="page-indicator")
                with Container(id="buttons-container"):
                    with Horizontal(id="navigation-buttons"):
                        yield Button("Back", id="back-button", classes="nav-button")
                        yield Button(
                            "Next",
                            id="next-button",
                            classes="nav-button",
                            variant="primary",
                        )
                        yield Button("Close", id="close-button", classes="nav-button")

    def on_mount(self) -> None:
        """Set up the modal after mounting."""
        self.update_page()

    def update_page(self) -> None:
        """Update the displayed page content and navigation buttons."""
        # Mark current page as visited
        self.visited_pages.add(self.current_page)

        # Update page content
        content_widget = self.query_one("#page-content", Markdown)
        content_widget.update(self.get_page_content())

        # Update page indicator
        page_indicator = self.query_one("#page-indicator", Static)
        page_indicator.update(f"Page {self.current_page + 1} of {self.total_pages}")

        # Update progress sidebar
        for i in range(self.total_pages):
            progress_item = self.query_one(f"#progress-item-{i}", Static)
            # Remove all progress classes first
            progress_item.remove_class(
                "progress-item-current",
                "progress-item-visited",
                "progress-item-unvisited",
            )
            # Add appropriate class
            if i == self.current_page:
                progress_item.add_class("progress-item-current")
                progress_item.update(f"▶ {i + 1}. {self.page_titles[i]}")
            elif i in self.visited_pages:
                progress_item.add_class("progress-item-visited")
                progress_item.update(f"✓ {i + 1}. {self.page_titles[i]}")
            else:
                progress_item.add_class("progress-item-unvisited")
                progress_item.update(f"  {i + 1}. {self.page_titles[i]}")

        # Show/hide resource sections (only on page 1)
        resource_sections = self.query_one("#resource-sections", Container)
        resource_sections.display = self.current_page == 0

        # Update button visibility and states
        back_button = self.query_one("#back-button", Button)
        next_button = self.query_one("#next-button", Button)

        # Update back button label and state
        if self.current_page == 0:
            back_button.disabled = True
            back_button.label = "Back"
        else:
            back_button.disabled = False
            prev_title = self.page_titles[self.current_page - 1]
            back_button.label = f"← {prev_title}"

        # Update next button label
        if self.current_page == self.total_pages - 1:
            next_button.label = "Finish"
        else:
            next_title = self.page_titles[self.current_page + 1]
            next_button.label = f"{next_title} (Next →)"

        # Focus the appropriate button
        if self.current_page == 0:
            next_button.focus()
        else:
            next_button.focus()

        # Scroll content to top
        self.query_one("#onboarding-content", VerticalScroll).scroll_home(animate=False)

    def get_page_content(self) -> str:
        """Get the content for the current page."""
        if self.current_page == 0:
            return self._page_1_resources()
        elif self.current_page == 1:
            return self._page_2_modes()
        elif self.current_page == 2:
            return self._page_3_prompts()
        else:
            return self._page_4_context_management()

    def _page_1_resources(self) -> str:
        """Page 1: Helpful resources."""
        return """
## Getting Started Resources

Here are some helpful resources to get you up to speed with Shotgun:
"""

    def _page_2_modes(self) -> str:
        """Page 2: Explanation of the 5 modes."""
        return """
## Understanding Shotgun's 5 Modes

Shotgun has 5 specialized modes, each designed for specific tasks. Each mode writes to its own dedicated file in `.shotgun/`:

### 🔬 Research Mode
Research topics with web search and synthesize findings. Perfect for gathering information and exploring new concepts.

**Writes to:** `.shotgun/research.md`

### 📝 Specify Mode
Create detailed specifications and requirements documents. Great for planning features and documenting requirements.

**Writes to:** `.shotgun/specification.md`

### 📋 Plan Mode
Create comprehensive, actionable plans with milestones. Ideal for breaking down large projects into manageable steps.

**Writes to:** `.shotgun/plan.md`

### ✅ Tasks Mode
Generate specific, actionable tasks from research and plans. Best for getting concrete next steps and action items.

**Writes to:** `.shotgun/tasks.md`

### 📤 Export Mode
Export artifacts and findings to various formats. Creates documentation like Claude.md (AI instructions), Agent.md (agent specs), PRDs, and other deliverables. Can write to any file in `.shotgun/` except the mode-specific files above.

**Writes to:** `.shotgun/Claude.md`, `.shotgun/Agent.md`, `.shotgun/PRD.md`, etc.

---

**Tip:** You can switch between modes using `Shift+Tab` or `Ctrl+P` to open the command palette!
"""

    def _page_3_prompts(self) -> str:
        """Page 3: Tips for better prompts."""
        return """
## Writing Better Prompts

Here are some tips to get the best results from Shotgun:

### 1. Ask for Research First
Before jumping into a task, ask Shotgun to research the codebase or topic:

> "Can you research how authentication works in this codebase?"

### 2. Request Clarifying Questions
Let Shotgun ask you questions to better understand your needs:

> "I want to add user profiles. Please ask me clarifying questions before starting."

### 3. Be Specific About Context
Provide relevant context about what you're trying to accomplish:

> "I'm working on the payment flow. I need to add support for refunds."

### 4. Use the Right Mode
Switch to the appropriate mode for your task:
- Use **Research** for exploration
- Use **Specify** for requirements
- Use **Plan** for implementation strategy
- Use **Tasks** for actionable next steps

---

**Remember:** Shotgun works best when you give it context and let it ask questions!
"""

    def _page_4_context_management(self) -> str:
        """Page 4: Context management and conversation controls."""
        return """
## Managing Conversation Context

As conversations grow, you may need to manage the context sent to the AI model.

### Clear Conversation
Completely start over with a fresh conversation.

**How to use:**
- Open Command Palette: `Ctrl+P`
- Type: "Clear Conversation"
- Confirm the action

**When to use:**
- Starting a completely new task or project
- When you want a clean slate
- Context has become too cluttered

---

### Compact Conversation
Intelligently compress the conversation history while preserving important context.

**How to use:**
- Open Command Palette: `Ctrl+P`
- Type: "Compact Conversation"
- Shotgun will compress older messages automatically

**When to use:**
- Conversation is getting long but you want to keep context
- Running into token limits
- Want to reduce costs while maintaining continuity

**What it does:**
- Summarizes older messages
- Keeps recent messages intact
- Preserves key information and decisions

---

**Tip:** Use `Ctrl+U` to view your current usage and see how much context you're using!
"""

    @on(Button.Pressed, "#back-button")
    def handle_back(self) -> None:
        """Handle back button press."""
        if self.current_page > 0:
            self.current_page -= 1
            self.update_page()

    @on(Button.Pressed, "#next-button")
    def handle_next(self) -> None:
        """Handle next/finish button press."""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_page()
        else:
            # On last page, finish closes the modal
            self.dismiss()

    @on(Button.Pressed, "#close-button")
    def handle_close(self) -> None:
        """Handle close button press."""
        self.dismiss()

    @on(Button.Pressed, "#youtube-button")
    def handle_youtube(self) -> None:
        """Open demo section in README."""
        webbrowser.open(
            "https://github.com/shotgun-sh/shotgun?tab=readme-ov-file#-demo"
        )

    @on(Button.Pressed, "#usage-button")
    def handle_usage_guide(self) -> None:
        """Open usage guide in browser."""
        webbrowser.open(
            "https://github.com/shotgun-sh/shotgun?tab=readme-ov-file#-usage"
        )
