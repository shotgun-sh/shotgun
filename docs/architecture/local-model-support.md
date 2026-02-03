# Local Model Support Architecture

This document describes how Shotgun supports local LLMs via Ollama and LM Studio.

## Overview

Shotgun provides local LLM support by abstracting local providers (Ollama and LM Studio) as OpenAI-compatible providers. The system automatically detects model capabilities, filters incompatible models, and adjusts operational modes based on model limitations.

### Supported Local Providers

| Provider | Default Port | Model Listing API | Capability Detection |
|----------|-------------|-------------------|---------------------|
| Ollama | 11434 | `/api/tags` | `/api/show` (template-based) |
| LM Studio | 1234 | `/v1/models` | Assumed (OpenAI-compatible) |

## Key Components

### 1. Local Provider Services

#### Ollama Service (`src/shotgun/tui/services/ollama.py`)

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

#### LM Studio Service (`src/shotgun/tui/services/lm_studio.py`)

The service for interacting with local LM Studio instances.

**Models:**
- `LMStudioModel` - Represents a model with id, object, and owned_by fields
- `LMStudioStatus` - Status of the LM Studio instance (running, models, error)

**Key Functions:**
- `get_lm_studio_status()` - Checks if LM Studio is running and lists available models

**Capability Assumptions:**
- Tool support is assumed for all LM Studio models (most models loaded support function calling)
- Vision support is conservatively set to False (LM Studio doesn't expose this via API)

### 2. Configuration System (`src/shotgun/agents/config/`)

**OllamaConfig** (in `models.py`):
```python
class OllamaConfig(BaseModel):
    enabled: bool = False
    base_url: str = "http://localhost:11434"
```

**LMStudioConfig** (in `models.py`):
```python
class LMStudioConfig(BaseModel):
    enabled: bool = False
    base_url: str = "http://localhost:1234"
```

**Model Identification:**
- Ollama models are prefixed with `"ollama/"` (e.g., `"ollama/llama3:8b"`)
- LM Studio models are prefixed with `"lmstudio/"` (e.g., `"lmstudio/lmstudio-community/Meta-Llama-3-8B"`)
- Helper functions: `is_ollama_model()`, `get_ollama_model_name()`, `is_lm_studio_model()`, `get_lm_studio_model_name()`

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
3. LM Studio model (if selected and enabled)
4. Cloud providers (Shotgun Account, BYOK)
```

### 4. UI Components

**Model Picker** (`src/shotgun/tui/screens/model_picker.py`):
- Displays cloud models and local models in separate tabs:
  - Cloud Models tab
  - Ollama tab
  - LM Studio tab
- **Filters models without tool support** (Ollama only) - disabled with "No tool support" label
- Shows status: "X/Y model(s) support tools (Experimental)"

**Provider Config** (`src/shotgun/tui/screens/provider_config.py`):
- Ollama tab for enable/disable toggle with installation link
- LM Studio tab for enable/disable toggle with installation link

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
  "lm_studio": {
    "enabled": true,
    "base_url": "http://localhost:1234"
  },
  "selected_model": "ollama/llama3:8b"
}
```

For LM Studio:
```json
{
  "selected_model": "lmstudio/lmstudio-community/Meta-Llama-3-8B-Instruct-GGUF"
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

To add support for another OpenAI-compatible local provider (as was done for LM Studio):

1. Create a new service file (e.g., `src/shotgun/tui/services/lm_studio.py`) with:
   - Model and Status Pydantic classes
   - `get_<provider>_status()` function
   - `sanitize_<provider>_model_name_for_id()` helper
2. Add configuration model in `config/models.py`:
   - `<Provider>Config` class with `enabled` and `base_url` fields
   - `<PROVIDER>_MODEL_PREFIX` constant (e.g., `"lmstudio/"`)
   - `<PROVIDER>_PLACEHOLDER_API_KEY` constant
   - `is_<provider>_model()` TypeGuard function
   - `get_<provider>_model_name()` helper
   - `get_<provider>_api_base_url()` helper
3. Update `config/manager.py`:
   - Add migration function (increment config version)
   - Add `update_<provider>_enabled()` and `is_<provider>_enabled()` methods
4. Update `config/provider.py`:
   - Import new helpers
   - Add priority check in `get_provider_model()`
   - Handle prefix stripping in `_create_openai_compat_model()`
5. Update TUI screens:
   - Add new tab in `provider_config.py`
   - Add new tab in `model_picker.py`
   - Add event handlers for enable/install buttons
6. Add tests for the new service
7. Update this documentation
