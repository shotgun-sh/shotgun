# Configuration Management

This directory contains the configuration management system for Shotgun, including models, migrations, and provider integration.

## Config Version History

### Version 1 (Config Versioning Introduced)

- **Commit**: `f36defc` (Sep 19, 2025)
- **Title**: "feat: add Sentry error tracking with anonymous user identification"
- **Key Fields**: `user_id`, `config_version: 1`
- **Note**: First version to include explicit versioning

### Version 2 (Shotgun Account Provider)

- **Commit**: `37a5add` (Oct 3, 2025)
- **Title**: "feat: add Shotgun Account provider with LiteLLM proxy support"
- **Key Fields**: `user_id`, `config_version: 2`, added `shotgun` provider config
- **Note**: Configs without a version field default to v2 during migration

### Version 3 (OAuth Authentication)

- **Commit**: `39d2af9` (Oct 6, 2025)
- **Title**: "feat: implement OAuth-style authentication flow for Shotgun Account"
- **Key Changes**:
  - Renamed `user_id` → `shotgun_instance_id`
  - Added `supabase_jwt` field to Shotgun Account config
- **Git Tags**: Both `0.2.11.dev1` and `0.2.11.dev2` are at this version

### Version 4 (Marketing Messages)

- **Commit**: `8638a6d` (Nov 4, 2025)
- **Title**: "feat: add marketing message system for GitHub star promotion"
- **Key Changes**:
  - Added `marketing` configuration with message tracking
  - Added `shown_welcome_screen` field (set to `False` for existing BYOK users)

### Version 5 (Streaming Detection) - CURRENT

- **Commit**: `fded351` (Nov 6, 2025)
- **Title**: "feat: add config migration for streaming capability field (v4->v5)"
- **Key Changes**:
  - Added `supports_streaming` field to OpenAI config
  - Added `supabase_jwt` to Shotgun Account config

## Migration System

The migration system is designed to be sequential and idempotent. Migrations are defined in `manager.py`:

- `_migrate_v2_to_v3()`: Renames `user_id` to `shotgun_instance_id`
- `_migrate_v3_to_v4()`: Adds marketing config and welcome screen flag
- `_migrate_v4_to_v5()`: Adds streaming support fields

All migrations preserve user data (API keys, settings) and can be safely run multiple times.

## Adding a New Config Version

When adding a new config version:

1. **Update `models.py`**:
   - Increment `CURRENT_CONFIG_VERSION` constant
   - Add new fields to appropriate config models

2. **Create migration function in `manager.py`**:
   ```python
   def _migrate_vN_to_vN+1(data: dict[str, Any]) -> dict[str, Any]:
       """Migrate config from version N to N+1."""
       data["config_version"] = N + 1
       # Add migration logic
       return data
   ```

3. **Register migration**:
   - Add to `migrations` dict in `_apply_migrations()`

4. **Add tests in `test/unit/test_config_migrations.py`**:
   - Create example config for version N
   - Test individual migration function
   - Test sequential migration from version N to current
   - Test with populated configs (non-empty API keys, etc.)
   - Test edge cases

## Files

- **`models.py`**: Pydantic models for configuration schema
- **`manager.py`**: ConfigManager class and migration functions
- **`provider.py`**: LLM provider integration and model creation
- **`streaming_test.py`**: OpenAI streaming capability detection
