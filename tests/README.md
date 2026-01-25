# KidSearch Test Suite

Comprehensive test suite for the KidSearch application, covering API endpoints, services, and integration tests.

## Test Structure

```
tests/
├── conftest.py                 # Shared fixtures and configuration
├── api/                        # API endpoint tests
│   ├── test_health.py         # Health endpoint tests
│   └── test_models.py         # Pydantic model validation tests
├── services/                   # Service layer tests
│   ├── test_typesense_client.py  # Typesense client tests
│   ├── test_merger.py         # Search merger service tests
│   ├── test_safety.py         # Safety filter tests
│   └── test_stats_db.py       # Stats database tests
└── integration/                # Integration tests
    └── test_search_flow.py    # End-to-end search flow tests
```

## Running Tests

### Install test dependencies

```bash
pip install -r tests/requirements-test.txt
```

### Run all tests

```bash
pytest
```

### Run specific test categories

```bash
# Unit tests only
pytest -m unit

# API tests only
pytest -m api

# Integration tests only
pytest -m integration

# Exclude slow tests
pytest -m "not slow"
```

### Run with coverage

```bash
pytest --cov=kidsearch --cov-report=html
```

This will generate a coverage report in `htmlcov/index.html`.

### Run specific test files

```bash
# Test Typesense client
pytest tests/services/test_typesense_client.py

# Test API endpoints
pytest tests/api/

# Test integration
pytest tests/integration/
```

## Test Markers

Tests are marked with the following markers:

- `unit`: Unit tests for individual components
- `integration`: Integration tests for complete flows
- `api`: API endpoint tests
- `services`: Service layer tests
- `slow`: Slow-running tests (can be excluded for quick runs)

## Writing Tests

### Example test structure

```python
import pytest

@pytest.mark.unit
def test_something(sample_fixture):
    """Test description"""
    # Arrange
    data = {"key": "value"}

    # Act
    result = process_data(data)

    # Assert
    assert result == expected_value
```

### Using fixtures

Common fixtures are defined in `conftest.py`:

- `api_client`: FastAPI test client
- `mock_typesense_client`: Mock Typesense client
- `sample_search_result`: Sample search result for testing
- `temp_db_path`: Temporary database path for testing

### Async tests

For testing async functions:

```python
@pytest.mark.asyncio
async def test_async_function(async_mock_typesense_client):
    result = await my_async_function()
    assert result is not None
```

## Continuous Integration

Tests are automatically run on:
- Every push to main
- Every pull request
- Scheduled daily runs

CI configuration can be found in `.github/workflows/test.yml`.

## Coverage Goals

- Overall coverage: > 80%
- Critical paths: > 90%
- New features: 100%

## Troubleshooting

### Tests fail with import errors

Ensure the project is installed in development mode:

```bash
pip install -e .
```

### Async tests not running

Install pytest-asyncio:

```bash
pip install pytest-asyncio
```

### Database tests fail

Ensure you have write permissions to the temp directory and no stale database files exist.
