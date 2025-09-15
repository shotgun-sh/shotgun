# Shotgun Test Suite

This directory contains the complete test suite for Shotgun, organized by test type.

## Directory Structure

```
test/
├── unit/           # Unit tests (fast, no external dependencies)
├── integration/    # Integration tests (slower, requires LLM setup)
└── README.md       # This file
```

## Unit Tests (`test/unit/`)

Unit tests are fast, isolated tests that don't require external services or LLM configuration. They test individual components in isolation with mocked dependencies.

**Characteristics:**
- Fast execution (< 1 second per test)
- No network calls or external dependencies
- Use mocks and stubs for dependencies
- Can be run in any environment
- Part of CI/CD pipeline

**Running unit tests:**
```bash
# Run all unit tests
pytest test/unit/

# Run specific test file
pytest test/unit/test_config_manager.py

# Run with coverage
pytest test/unit/ --cov=src/shotgun --cov-report=html
```

## Integration Tests (`test/integration/`)

Integration tests verify the complete functionality of the CodebaseService, including:
- Real graph creation from codebases
- Actual LLM queries (natural language to Cypher)
- End-to-end query execution
- Error handling and edge cases

**Characteristics:**
- Slower execution (several seconds to minutes)
- Requires LLM API configuration
- Creates real databases and graphs
- Tests complete workflows
- May be skipped in some CI environments

**Requirements:**
- LLM API keys (OpenAI or Anthropic)
- Proper Shotgun configuration
- More disk space and memory

**Running integration tests:**
```bash
# Run all integration tests
pytest test/integration/

# Run with verbose output
pytest test/integration/ -v -s

# Run specific test
pytest test/integration/test_codebase_service.py::TestCodebaseService::test_create_graph

# Run smoke test only
python test/integration/run_integration_tests.py --smoke-only

# Run comprehensive test only
python test/integration/run_integration_tests.py --comprehensive-only
```

## Environment Setup

### For Unit Tests
No special setup required. Just install dependencies:
```bash
uv sync --all-extras
```

### For Integration Tests
1. Install dependencies:
   ```bash
   uv sync --all-extras
   ```

2. Configure LLM provider (one of):
   ```bash
   # For OpenAI
   export OPENAI_API_KEY="your_api_key"
   
   # For Anthropic
   export ANTHROPIC_API_KEY="your_api_key"
   ```

3. Run environment check:
   ```bash
   python test/integration/run_integration_tests.py --smoke-only
   ```

## Test Markers

Tests use pytest markers to categorize them:

- `@pytest.mark.integration` - Integration test requiring LLM
- `@pytest.mark.slow` - Test that takes significant time  
- `@pytest.mark.llm` - Test that makes actual LLM API calls

## Running Specific Test Categories

```bash
# Run only integration tests
pytest -m integration

# Run only fast tests (exclude slow ones)
pytest -m "not slow"

# Run tests that don't require LLM calls
pytest -m "not llm"
```

## CI/CD Integration

### Unit Tests in CI
Unit tests should run on every commit and PR:
```yaml
- name: Run unit tests
  run: |
    uv run pytest test/unit/ --cov=src/shotgun --cov-report=xml
    
- name: Upload coverage
  uses: codecov/codecov-action@v3
```

### Integration Tests in CI
Integration tests can be run on specific branches or with environment variables:
```yaml
- name: Run integration tests
  if: github.ref == 'refs/heads/main' && env.OPENAI_API_KEY != ''
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
  run: |
    uv run python test/integration/run_integration_tests.py
```

## Writing New Tests

### Unit Tests
1. Add test file to `test/unit/`
2. Use mocks for external dependencies
3. Test single components in isolation
4. Keep tests fast (< 1 second each)

Example:
```python
import pytest
from unittest.mock import Mock, patch

def test_my_function():
    # Arrange
    mock_dependency = Mock()
    
    # Act
    result = my_function(mock_dependency)
    
    # Assert
    assert result is not None
    mock_dependency.some_method.assert_called_once()
```

### Integration Tests
1. Add test file to `test/integration/`
2. Use real services and dependencies
3. Test complete workflows
4. Mark with appropriate decorators

Example:
```python
import pytest
from shotgun.codebase import CodebaseService, QueryType

@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_workflow(temp_storage_dir, sample_codebase):
    service = CodebaseService(temp_storage_dir)
    
    # Create graph
    graph = await service.create_graph(sample_codebase, "Test Graph")
    
    # Execute query
    result = await service.execute_query(
        graph.graph_id,
        "Show me all classes",
        QueryType.NATURAL_LANGUAGE
    )
    
    assert result.success
    assert result.row_count > 0
```

## Troubleshooting

### Common Issues

1. **Import errors in tests**: Make sure `src/` is in Python path
2. **LLM API errors**: Check API keys and rate limits
3. **Timeout errors**: Increase timeout for slow integration tests
4. **Database errors**: Ensure temp directories have write permissions

### Debug Mode
Run tests with more verbose output:
```bash
pytest test/integration/ -v -s --tb=long --log-cli-level=DEBUG
```

### Test Data Cleanup
Integration tests use temporary directories that are automatically cleaned up. If you need to inspect test data:
```bash
# Set environment variable to preserve temp directories
export PYTEST_CURRENT_TEST_KEEP_TEMP=1
pytest test/integration/test_codebase_service.py::test_create_graph -s
```