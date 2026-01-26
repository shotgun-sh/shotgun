# Testing the Shotgun TUI with Playwright MCP

This guide documents how to test the Shotgun TUI using the Playwright MCP server. Since Textual renders to a canvas element via xterm.js, standard accessibility-based testing doesn't work - these techniques use screenshots and keyboard navigation instead.

## Architecture Overview

When running `shotgun --web`, the TUI is served via `textual-serve` which:
1. Renders the Textual app to a pseudo-terminal
2. Streams the output to xterm.js in the browser via WebSocket
3. Sends keyboard input from the browser back to the app

A **custom HTML template** (`src/shotgun/tui/templates/app_index.html`) extends the default textual-serve template with:
- WebSocket interception for debugging
- A `window.shotgunTest` JavaScript API (see "Testing API" section)
- Test status indicator when `?testing` query param is used

## Starting the TUI Web Server

Launch the TUI in web mode with a specific port:

```bash
uv run shotgun --web --port 8765 --no-update-check
```

Run this in the background so you can interact with it via Playwright:

```bash
# Using Claude Code's background execution
uv run shotgun --web --port 8765 --no-update-check &
```

Wait 2-3 seconds for the server to start before navigating to it.

**For testing with the debug indicator**, add `?testing` to the URL:
```
http://localhost:8765/?testing
```

## Efficient Testing Strategy

### Parallel Monitoring

While waiting for agent processing, use file system monitoring to track progress:

```bash
# Watch .shotgun folder for new files
watch -n 2 'ls -la .shotgun/*.md 2>/dev/null; ls -la .shotgun/contracts/ 2>/dev/null'

# Or use ls in a loop
while true; do ls -la .shotgun/*.md 2>/dev/null; sleep 5; done
```

### Recommended Wait Times

Different operations need different wait times:
- **Navigation/screen transitions**: 2-3 seconds
- **Simple agent responses**: 30-45 seconds
- **Research phase** (web searches): 90-120 seconds
- **Specification writing**: 60-90 seconds
- **Plan/Tasks generation**: 60-90 seconds

### Skip Codebase Indexing Quickly

The indexing prompt requires navigating to "Not now". Use this sequence:
```javascript
// Skip indexing prompt efficiently
await page.keyboard.press('Shift+Tab');
await page.keyboard.press('Shift+Tab');
await page.waitForTimeout(300);
await page.keyboard.press('Enter');
```

### Typing "continue" to Proceed Through Steps

Shotgun's workflow requires typing "continue" between steps:
```javascript
await page.click('.xterm-screen');
await page.waitForTimeout(500);
await page.keyboard.type('continue', { delay: 50 });
await page.waitForTimeout(300);
await page.keyboard.press('Enter');
```

### Monitor Multiple Sources

While agent is processing, check these in parallel (using separate terminal):
1. **Screenshots** - Visual state of TUI
2. **Log files** - `tail -f ~/.shotgun-sh/logs/$(ls -t ~/.shotgun-sh/logs/ | head -1)`
3. **Generated files** - `ls -la .shotgun/`
4. **Conversation** - `cat ~/.shotgun-sh/conversation.json | jq '.agent_history | length'`

## Key Testing Principles

### 0. CRITICAL: Wait for Agent Processing to Complete

**This is the most important rule.** When the Shotgun agent is processing a request (working), DO NOT send any Playwright commands. Any keyboard input or interaction will cancel the current operation.

**How to know when the agent is working:**
- The status bar shows a spinner or "working" indicator
- The agent is streaming a response
- You just pressed Enter to send a message

**What to do:**
- After sending a message with Enter, wait for the FULL response to complete
- Use `browser_wait_for` with generous timeouts (30-60 seconds for complex requests)
- Take a screenshot ONLY after the agent has finished responding
- Look for the input prompt to become active again before sending more commands

**Signs the agent is done:**
- No more text being streamed
- Input field shows the placeholder text again
- Status bar no longer shows working/spinner state

**Example - WRONG:**
```
browser_press_key: Enter     # Send message
browser_wait_for: time=2     # TOO SHORT - agent still working
browser_take_screenshot      # This interrupts the agent!
```

**Example - CORRECT:**
```
browser_press_key: Enter     # Send message
browser_wait_for: time=45    # Wait long enough for full response
browser_take_screenshot      # Safe to screenshot now
```

### 1. Screenshots Over Accessibility Snapshots

Textual renders the TUI in an xterm canvas element. The Playwright accessibility snapshot (`browser_snapshot`) only sees:

```yaml
- generic [ref=e11]:
  - generic:
    - textbox "Terminal input"
```

**Always use `browser_take_screenshot`** to see what's actually displayed. Screenshots show the full rendered TUI including:
- Screen content and text
- Button states and focus indicators
- Mode indicators and status bars
- Modal dialogs and command palettes

### 2. Keyboard Navigation is Primary

Since there's no accessible DOM structure for the rendered content, use keyboard navigation.

**Keyboard shortcuts:**
- `Tab` - Move focus between elements
- `Enter` - Select/activate the focused element
- `Escape` - Close modals and dialogs
- `Shift+Tab` - Toggle between Planning and Drafting mode
- `/` - Open the command palette
- `Ctrl+j` - Add a newline in the input field
- `Ctrl+c` - Copy
- `Ctrl+v` - Paste

### 3. Typing Text

The input field is an xterm canvas, not a regular input. To type text:

```javascript
// First click to focus the terminal
await page.click('.xterm-screen');
// Then type the message
await page.keyboard.type('Your message here', { delay: 50 });
```

Using the MCP tools:
1. Use `browser_run_code` with the above pattern
2. Press `Enter` to send the message

**Do NOT use** `browser_type` or `browser_fill_form` - these require standard form elements.

## Testing Workflow

### Step 1: Navigate to the TUI

```
browser_navigate: http://localhost:8765
```

Wait 2-3 seconds for the page to load:

```
browser_wait_for: time=3
```

### Step 2: Take Initial Screenshot

```
browser_take_screenshot: filename=tui-initial.png
```

This shows what screen you're on (e.g., codebase indexing prompt, welcome, chat).

### Step 3: Navigate Through Screens

Use Tab and Enter to navigate:

```
browser_press_key: Tab    # Move focus
browser_take_screenshot   # Verify focus moved (look for highlight/border)
browser_press_key: Enter  # Select
browser_wait_for: time=2  # Wait for transition
browser_take_screenshot   # Verify new screen
```

### Step 4: Test Chat Interaction

```javascript
// Type a message
browser_run_code: async (page) => {
  await page.click('.xterm-screen');
  await page.keyboard.type('Hello, can you tell me about yourself?', { delay: 50 });
}

// Send it
browser_press_key: Enter

// Wait for response
browser_wait_for: time=5

// Capture the response
browser_take_screenshot: filename=chat-response.png
```

### Step 5: Test Command Palette (Optional)

The command palette (`/`) provides access to settings and utilities. Skip this during spec generation workflows - focus on the chat interaction instead.

### Step 6: Test Mode Toggle

```
browser_press_key: Shift+Tab
browser_take_screenshot   # Verify mode changed in status bar
```

## Common Screens to Test

### 1. Codebase Index Prompt Screen
- Shows "Want to index your codebase?"
- Two buttons: "Not now" and "Index now"
- Tab moves focus between buttons

### 2. Main Chat Screen
- Shows welcome message
- Input prompt at bottom
- Status bar showing: mode, context window %, model name
- Keyboard shortcuts reference

### 3. Command Palette
- Opened with `/`
- Filterable list of commands
- Navigate with arrow keys, select with Enter

### 4. Context Analysis Display
- Shows token usage breakdown
- Model name, total context, free space
- Composition by message type

## Verifying UI State

Since you can't query DOM elements, verify state by:

1. **Taking screenshots** and describing what you see
2. **Checking status bar** text (visible at bottom of screenshots)
3. **Looking for visual indicators**:
   - Focus: bordered/highlighted elements
   - Mode: "Planning mode" vs "Drafting mode" in status bar
   - Working state: spinner or "working" indicator

## Example: Full Test Session

```python
# 1. Start server (in background)
# uv run shotgun --web --port 8765 --no-update-check

# 2. Navigate
browser_navigate(url="http://localhost:8765")
browser_wait_for(time=3)
browser_take_screenshot(filename="01-initial.png")

# 3. Skip codebase indexing
browser_press_key(key="Tab")  # Focus "Not now"
browser_take_screenshot(filename="02-focused-not-now.png")
browser_press_key(key="Enter")  # Click it
browser_wait_for(time=2)
browser_take_screenshot(filename="03-chat-screen.png")

# 4. Send a message
browser_run_code(code="""async (page) => {
  await page.click('.xterm-screen');
  await page.keyboard.type('What can you help me with?', { delay: 50 });
}""")
browser_press_key(key="Enter")
browser_wait_for(time=5)
browser_take_screenshot(filename="04-response.png")

# 5. Open command palette
browser_press_key(key="/")
browser_take_screenshot(filename="05-command-palette.png")

# 6. Select "Show usage"
browser_run_code(code="""async (page) => {
  await page.keyboard.type('show usage');
}""")
browser_press_key(key="Enter")
browser_wait_for(time=2)
browser_take_screenshot(filename="06-usage.png")

# 7. Toggle mode
browser_press_key(key="Shift+Tab")
browser_take_screenshot(filename="07-mode-toggled.png")

# 8. Clean up - kill the background server
```

## Troubleshooting

### "Operation cancelled by user" messages appear
- **This means you sent a command while the agent was still processing**
- You MUST wait for the agent to fully complete its response before any interaction
- Use longer wait times: `browser_wait_for: time=45` or more for complex requests
- Only take screenshots or send input AFTER the agent is completely done

### Screenshots show blank/loading screen
- Wait longer after navigation (`browser_wait_for: time=5`)
- The TUI takes time to initialize

### Keyboard input not working
- Make sure to click `.xterm-screen` first to focus
- Use `browser_run_code` for typing, not `browser_type`

### Can't dismiss modal
- Try `Escape` multiple times
- Some "modals" are actually inline hint messages that don't dismiss
- Check screenshot to see if it's truly a modal or inline content

### Mode toggle not working
- Ensure input field is focused (click `.xterm-screen` first)
- Use `Shift+Tab` not just `Tab`

## Debugging and Monitoring

### Log Files

Shotgun logs are stored in `~/.shotgun-sh/logs/` with timestamped filenames.

**Get the latest log file:**
```bash
ls -t ~/.shotgun-sh/logs/ | head -1
```

**Tail the current session's logs:**
```bash
tail -f ~/.shotgun-sh/logs/$(ls -t ~/.shotgun-sh/logs/ | head -1)
```

**Search logs for specific events:**
```bash
# Find all web searches
grep "web_search_tool" ~/.shotgun-sh/logs/$(ls -t ~/.shotgun-sh/logs/ | head -1)

# Find file operations
grep "Writing file\|Reading file" ~/.shotgun-sh/logs/$(ls -t ~/.shotgun-sh/logs/ | head -1)

# Find errors
grep "ERROR" ~/.shotgun-sh/logs/$(ls -t ~/.shotgun-sh/logs/ | head -1)
```

### Conversation History

The conversation is persisted to `~/.shotgun-sh/conversation.json`.

**Check message count:**
```bash
cat ~/.shotgun-sh/conversation.json | jq '.agent_history | length'
```

**See recent tool calls:**
```bash
cat ~/.shotgun-sh/conversation.json | jq '.agent_history[].parts[]? | select(.kind == "tool-call") | .tool_name' | tail -20
```

### Generated Files

Shotgun writes specs and research to `.shotgun/` in the working directory.

**Monitor file creation:**
```bash
ls -la .shotgun/
ls -la .shotgun/research/
```

**Check research index:**
```bash
cat .shotgun/research.md
```

**Count tokens in generated files:**
```bash
uv run python scripts/count_tokens.py .shotgun/
```

This shows token counts per file and folder, useful for understanding context usage.

### Why So Many Web Searches?

The Research agent is designed to be thorough. It often runs multiple parallel web searches to gather comprehensive information on different aspects of a topic. This is expected behavior when researching complex technical topics.

To understand what's happening:
1. Check the logs for `web_search_tool` entries
2. Look at `.shotgun/research.md` to see what findings are being compiled
3. Each search query is logged with its result preview

## Screenshots Directory

Playwright MCP saves screenshots to: `.playwright-mcp/`

This directory is gitignored. Screenshots are useful for:
- Debugging test failures
- Documenting UI states
- Verifying visual changes

## Testing API (window.shotgunTest)

The custom template at `src/shotgun/tui/templates/app_index.html` provides a JavaScript API for automation. However, **it has known limitations**.

### What the API Provides

When navigating to `http://localhost:8765/?testing`, the template:
1. Intercepts WebSocket creation to capture the terminal connection
2. Exposes `window.shotgunTest` with methods like:
   - `init()` - Initialize the API
   - `pressKey(key)` - Send a key press (Tab, Enter, Escape, etc.)
   - `type(text)` - Send text
   - `pressEnter()`, `pressTab()`, `pressEscape()` - Convenience methods
3. Shows a green status indicator in the bottom-right corner

### Known Bug: WebSocket Input Unreliable

**The `shotgunTest` API sends keypresses via WebSocket but they often don't reach Textual widgets properly.** The keypresses are sent to the terminal but Textual's widget focus system doesn't always process them.

**What works:**
- The WebSocket connection is established correctly
- Keys are sent to the terminal (you can see the status indicator update)
- Basic Tab/Enter sometimes works for modal buttons after many presses

**What doesn't work reliably:**
- Typing text into input fields
- Opening command palette with `/`
- Complex keyboard sequences

### Recommended Approach: Use Playwright's Native Keyboard

Instead of the `shotgunTest` API, use Playwright's native keyboard which sends input through the browser's event system:

```javascript
// First click to focus the terminal
const terminal = await page.$('#terminal');
await terminal.click();
await page.waitForTimeout(300);

// Type text - this WORKS reliably
await page.keyboard.type('/model', { delay: 30 });
await page.waitForTimeout(500);
await page.keyboard.press('Enter');
```

This approach:
- Clicks the terminal element to ensure focus
- Uses `page.keyboard.type()` and `page.keyboard.press()` for input
- Works for both typing text and special keys

### When to Use Each Approach

| Task | Use This |
|------|----------|
| Typing text in input fields | `page.keyboard.type()` |
| Pressing special keys (Enter, Tab, Escape) | `page.keyboard.press()` |
| Arrow key navigation | `page.keyboard.press('ArrowUp')` |
| Debugging what keys are sent | `shotgunTest` API (check status indicator) |

### Example: Complete Interaction Pattern

```javascript
await page.evaluate(() => {
  // Optional: use for debugging
  shotgunTest.init();
});

// Click terminal to focus
const terminal = await page.$('#terminal');
await terminal.click();
await page.waitForTimeout(300);

// Type a command
await page.keyboard.type('/model', { delay: 30 });
await page.waitForTimeout(500);

// Press Enter
await page.keyboard.press('Enter');
await page.waitForTimeout(1000);

// Navigate with arrow keys
await page.keyboard.press('ArrowDown');
await page.waitForTimeout(200);
await page.keyboard.press('Enter');
```

### Skipping the Codebase Index Prompt

The modal has two buttons. Tab cycles through them:

```javascript
// Click terminal first
const terminal = await page.$('#terminal');
await terminal.click();
await page.waitForTimeout(200);

// Press Tab multiple times to cycle through focusable elements
// Then press Enter when "Not now" is focused
for (let i = 0; i < 5; i++) {
  await page.keyboard.press('Tab');
  await page.waitForTimeout(200);
}
await page.keyboard.press('Enter');
```

Note: The exact number of Tab presses may vary depending on which button has initial focus.
