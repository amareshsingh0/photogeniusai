# Testing Guide

Complete guide for testing PhotoGenius AI API.

## Setup

### Install Test Dependencies

```bash
pip install -r requirements-dev.txt
```

Includes: `pytest`, `pytest-asyncio`, `httpx`, `pytest-cov`

### Test Database

Create a separate test database:

```bash
# In PostgreSQL
CREATE DATABASE photogenius_test;

# Update .env.test
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/photogenius_test
```

Or use in-memory SQLite for faster tests (not recommended for integration tests).

## Running Tests

### All Tests

```bash
pytest
```

### Specific Test File

```bash
pytest app/tests/test_safety.py
```

### Specific Test Function

```bash
pytest app/tests/test_safety.py::test_prompt_sanitizer
```

### With Coverage

```bash
pytest --cov=app --cov-report=html --cov-report=term
```

View HTML report: `htmlcov/index.html`

### Verbose Output

```bash
pytest -v
```

### Stop on First Failure

```bash
pytest -x
```

## Test Structure

```
tests/
├── conftest.py           # Shared fixtures
├── test_api.py           # API endpoint tests
├── test_generation.py    # Generation service tests
├── test_safety.py        # Safety feature tests
└── test_prompt_sanitizer.py
```

## Writing Tests

### Basic Test Example

```python
# app/tests/test_example.py
import pytest
from app.services.safety.prompt_sanitizer import PromptSanitizer

@pytest.mark.asyncio
async def test_sanitizer_blocks_explicit_content():
    sanitizer = PromptSanitizer()
    result = await sanitizer.sanitize("explicit prompt")
    
    assert not result.is_safe
    assert len(result.violations) > 0
```

### Using Fixtures

```python
# conftest.py
import pytest
from app.core.database import AsyncSessionLocal

@pytest.fixture
async def db_session():
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()

# test_file.py
@pytest.mark.asyncio
async def test_with_db(db_session):
    # Use db_session
    pass
```

### Testing API Endpoints

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

### Testing Async Functions

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result is not None
```

## Test Categories

### Unit Tests

Test individual functions/classes in isolation:

```python
def test_prompt_sanitizer():
    sanitizer = PromptSanitizer()
    result = sanitizer.sanitize("test prompt")
    assert result.is_safe
```

### Integration Tests

Test multiple components working together:

```python
@pytest.mark.asyncio
async def test_generation_flow(db_session):
    # Test full generation flow
    # 1. Pre-check
    # 2. Generate
    # 3. Post-check
    # 4. Save to DB
    pass
```

### End-to-End Tests

Test complete API requests:

```python
def test_create_generation_e2e():
    response = client.post(
        "/api/v1/generations",
        json={"prompt": "professional headshot"},
        headers={"Authorization": "Bearer token"}
    )
    assert response.status_code == 200
```

## Mocking External Services

### Mock Redis

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_with_mocked_redis():
    with patch('app.services.safety.rate_limiter.redis_client') as mock_redis:
        mock_redis.get = AsyncMock(return_value=None)
        # Test rate limiter
        pass
```

### Mock S3

```python
from unittest.mock import patch

@patch('app.services.storage.s3_service.s3_client')
def test_upload_image(mock_s3):
    mock_s3.upload_fileobj.return_value = None
    # Test upload
    pass
```

### Mock AI Services

```python
@patch('app.services.ai.generation_service.generate_image')
async def test_generation(mock_generate):
    mock_generate.return_value = b"fake_image_data"
    # Test generation
    pass
```

## Test Data

### Fixtures for Test Data

```python
# conftest.py
@pytest.fixture
def sample_user():
    return {
        "id": "user_123",
        "email": "test@example.com",
        "role": "user"
    }

@pytest.fixture
def sample_prompt():
    return "professional headshot of a person"
```

### Using Factories

```python
# tests/factories.py
def create_user(**kwargs):
    defaults = {
        "id": "user_123",
        "email": "test@example.com"
    }
    defaults.update(kwargs)
    return defaults
```

## Testing Safety Features

### Prompt Sanitizer Tests

```python
@pytest.mark.asyncio
async def test_sanitizer_blocks_explicit():
    sanitizer = PromptSanitizer()
    result = await sanitizer.sanitize("explicit content")
    assert not result.is_safe

@pytest.mark.asyncio
async def test_sanitizer_allows_safe():
    sanitizer = PromptSanitizer()
    result = await sanitizer.sanitize("professional headshot")
    assert result.is_safe
```

### NSFW Classifier Tests

```python
@pytest.mark.asyncio
async def test_nsfw_classifier():
    classifier = NSFWClassifier()
    # Use test image
    result = await classifier.classify("path/to/test/image.jpg")
    assert result.action in ["ALLOW", "QUARANTINE", "BLOCK"]
```

### Age Estimator Tests

```python
@pytest.mark.asyncio
async def test_age_estimator_blocks_minor():
    estimator = AgeEstimator()
    result = await estimator.estimate_age("path/to/minor/image.jpg")
    assert not result.is_adult
    assert result.action == "BLOCK"
```

## Performance Testing

### Load Testing

```python
import asyncio

@pytest.mark.asyncio
async def test_concurrent_requests():
    tasks = [
        client.get("/api/v1/generations") 
        for _ in range(100)
    ]
    results = await asyncio.gather(*tasks)
    assert all(r.status_code == 200 for r in results)
```

### Benchmark Tests

```python
import time

def test_sanitizer_performance():
    sanitizer = PromptSanitizer()
    start = time.time()
    for _ in range(1000):
        sanitizer.sanitize("test prompt")
    duration = time.time() - start
    assert duration < 1.0  # Should complete in < 1 second
```

## Continuous Integration

### GitHub Actions Example

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pip install -r requirements-dev.txt
      - run: pytest --cov=app
```

## Test Coverage Goals

- **Unit Tests**: 80%+ coverage
- **Integration Tests**: Critical paths covered
- **E2E Tests**: Main user flows covered

## Best Practices

1. **Test Isolation**: Each test should be independent
2. **Use Fixtures**: Share common setup code
3. **Mock External Services**: Don't hit real APIs in tests
4. **Test Edge Cases**: Empty inputs, null values, large inputs
5. **Test Error Cases**: Invalid inputs, missing data
6. **Fast Tests**: Unit tests should run quickly
7. **Clear Names**: Test names should describe what they test
8. **Arrange-Act-Assert**: Structure tests clearly

## Debugging Tests

### Run with Print Statements

```python
def test_debug():
    result = some_function()
    print(f"Result: {result}")  # Will show in pytest output with -s
    assert result is not None
```

Run with: `pytest -s`

### Use PDB Debugger

```python
def test_with_debugger():
    result = some_function()
    import pdb; pdb.set_trace()  # Breakpoint
    assert result is not None
```

### Verbose Output

```bash
pytest -vv  # Very verbose
pytest -s    # Show print statements
pytest --pdb # Drop into debugger on failure
```

## Common Issues

### Database Connection Errors

- Ensure test database exists
- Check `DATABASE_URL` in test environment
- Use transactions that rollback after tests

### Async Test Issues

- Always use `@pytest.mark.asyncio`
- Use `await` for async functions
- Use `AsyncMock` for mocking async functions

### Import Errors

- Ensure you're running from project root
- Check `PYTHONPATH` is set correctly
- Verify virtual environment is activated

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
