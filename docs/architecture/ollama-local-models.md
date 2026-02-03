# Ollama/Local Model Support Architecture

This document describes how Shotgun supports local LLMs via Ollama.

## Overview

Shotgun provides local LLM support by abstracting Ollama as an OpenAI-compatible provider. The system automatically detects model capabilities, filters incompatible models, and adjusts operational modes based on model limitations.

## Key Components

### 1. Ollama Service (`src/shotgun/tui/services/ollama.py`)

The core service for interacting with local Ollama instances.

**Models:**
- `OllamaCapability` - Enum of supported capabilities: `COMPLETION`, `VISION`, `TOOLS`
- `OllamaModel` - Represents a model with name, size, and capabilities
- `OllamaStatus` - Status of the Ollama instance (running, models, error)

**Key Functions:**
- `get_ollama_status()` - Checks if Ollama is running and lists available models
- `get_model_capabilities()` - Queries `/api/show` to detect model capabilities

**Capability Detection:**
```python
# Tool support detection (required for Shotgun agents)
template = data.get("template", "")
if "{{.Tools}}" in template:
    capabilities.append(OllamaCapability.TOOLS)

# Vision support detection
arch = model_info.get("general.architecture", "")
if "clip" in arch.lower():
    capabilities.append(OllamaCapability.VISION)
```

### 2. Configuration System (`src/shotgun/agents/config/`)

**OllamaConfig** (in `models.py`):
```python
class OllamaConfig(BaseModel):
    enabled: bool = False
    base_url: str = "http://localhost:11434"
```

**Model Identification:**
- Ollama models are prefixed with `"ollama/"` (e.g., `"ollama/llama3:8b"`)
- Helper functions: `is_ollama_model()`, `get_ollama_model_name()`

### 3. Provider Integration (`src/shotgun/agents/config/provider.py`)

**Schema Transformation:**

Ollama has JSON schema limitations that require transformation:

```python
class OllamaCompatibleJsonSchemaTransformer:
    """Adapts JSON schemas for Ollama compatibility.

    - Inlines $defs references (Ollama doesn't support $ref)
    - Simplifies anyOf/oneOf nullable unions
    """
```

**Model Priority:**
```
1. OpenAI-compatible settings (env vars)
2. Ollama model (if selected and enabled)
3. Cloud providers (Shotgun Account, BYOK)
```

### 4. UI Components

**Model Picker** (`src/shotgun/tui/screens/model_picker.py`):
- Displays cloud and local models in separate tabs
- **Filters models without tool support** - disabled with "No tool support" label
- Shows status: "X/Y model(s) support tools (Experimental)"

**Provider Config** (`src/shotgun/tui/screens/provider_config.py`):
- Ollama tab for enable/disable toggle
- Shows installation link if Ollama not running

### 5. Mode Enforcement

**Problem:** Ollama models have inconsistent tool/function calling support.

**Solution:** Automatic Drafting mode (`src/shotgun/tui/screens/chat/chat_screen.py`):

```python
def _ensure_ollama_drafting_mode(self) -> None:
    """Force Drafting mode for Ollama models."""
    if is_ollama_model(model_name):
        self.agent_manager.router_mode = RouterMode.DRAFTING
```

This is called:
- On startup
- When screen resumes (after settings changes)
- After model selection

## Model Selection Flow

```
User selects Ollama model
    |
    v
ModelConfig created:
  - provider: OPENAI_COMPATIBLE
  - key_provider: BYOK
  - api_key: OLLAMA_PLACEHOLDER_API_KEY
  - base_url: http://localhost:11434
    |
    v
OpenAI-compatible Model created with OllamaCompatibleJsonSchemaTransformer
    |
    v
Chat screen validates model → _ensure_ollama_drafting_mode()
    |
    v
Drafting mode enabled (if Ollama model detected)
```

## Configuration Storage

**File:** `~/.shotgun-sh/config.json`

```json
{
  "ollama": {
    "enabled": true,
    "base_url": "http://localhost:11434"
  },
  "selected_model": "ollama/llama3:8b"
}
```

## Environment Variables

For advanced users, Ollama can be configured via environment variables:

| Variable | Description |
|----------|-------------|
| `SHOTGUN_OPENAI_COMPAT_BASE_URL` | Ollama endpoint URL |
| `SHOTGUN_OPENAI_COMPAT_API_KEY` | API key (use any value for Ollama) |

When these are set, they take priority over all other provider configuration.

## Limitations

1. **Tool Support Required** - Models without `{{.Tools}}` in their template cannot use Shotgun's agent features
2. **Drafting Mode Only** - Planning mode requires reliable tool calling, which Ollama models don't consistently support
3. **No PDF Support** - Ollama models don't support PDF input
4. **Vision Varies** - Only models with vision projectors (llava, clip-based) support images

## Adding Support for New Local Providers

To add support for another OpenAI-compatible local provider:

1. Create a new capability detection function in `ollama.py` (or new service)
2. Add configuration model in `config/models.py`
3. Update `get_provider_model()` in `config/provider.py` to handle the new provider
4. Add UI for configuration in `provider_config.py`
5. Ensure appropriate mode enforcement for provider limitations
