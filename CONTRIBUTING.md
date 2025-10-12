# Contributing to Exness Data Preprocess

Thank you for your interest in contributing to Exness Data Preprocess! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites

- Python 3.9 or higher
- uv package manager (recommended) or pip
- Git

### Clone and Setup

```bash
# Clone repository
git clone https://github.com/Eon-Labs/exness-data-preprocess.git
cd exness-data-preprocess

# Install with development dependencies
uv sync --dev

# Or with pip
pip install -e ".[dev]"
```

## Development Workflow

### Code Quality Standards

We maintain high code quality standards. All contributions must:

1. **Pass all tests**: Run `uv run pytest` before submitting
2. **Follow code style**: Use `uv run ruff format .` to format code
3. **Pass linting**: Run `uv run ruff check --fix .` to check and fix issues
4. **Pass type checking**: Run `uv run mypy src/` for type validation

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=exness_data_preprocess --cov-report=html

# Run specific test file
uv run pytest tests/test_processor.py -v

# Run specific test
uv run pytest tests/test_processor.py::test_compression_ratio -v
```

### Code Formatting

```bash
# Format all code
uv run ruff format .

# Check formatting without changes
uv run ruff format --check .
```

### Linting

```bash
# Lint and auto-fix
uv run ruff check --fix .

# Lint without changes
uv run ruff check .
```

## Contribution Guidelines

### Reporting Issues

When reporting issues, please include:

1. Python version (`python --version`)
2. Package version (`pip show exness-data-preprocess`)
3. Operating system and version
4. Minimal reproducible example
5. Expected vs actual behavior
6. Error messages and stack traces

### Submitting Pull Requests

1. **Fork the repository** and create a new branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following our code quality standards

3. **Add tests** for new functionality

4. **Update documentation** if needed (README.md, docstrings)

5. **Run all quality checks**:
   ```bash
   uv run ruff format .
   uv run ruff check --fix .
   uv run mypy src/
   uv run pytest
   ```

6. **Commit your changes** with clear messages:
   ```bash
   git commit -m "feat: add support for custom compression levels"
   ```

7. **Push to your fork** and submit a pull request:
   ```bash
   git push origin feature/your-feature-name
   ```

### Commit Message Conventions

We follow conventional commit format:

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `test:` Test additions or changes
- `refactor:` Code refactoring
- `perf:` Performance improvements
- `chore:` Build process or tooling changes

Examples:
```
feat: add support for multiple currency pairs
fix: handle timezone conversion edge case
docs: update compression benchmarks in README
test: add integration tests for DuckDB operations
```

## Code Organization

### Project Structure

```
exness-data-preprocess/
├── src/exness_data_preprocess/
│   ├── __init__.py          # Package entry point
│   ├── processor.py         # Core processor class
│   ├── api.py              # Simple API functions
│   └── cli.py              # Command-line interface
├── tests/
│   ├── conftest.py         # Pytest fixtures
│   ├── test_processor.py   # Processor tests
│   ├── test_api.py         # API tests
│   └── test_cli.py         # CLI tests
├── docs/                   # Documentation
├── pyproject.toml         # Package configuration
└── README.md             # Main documentation
```

### Adding New Features

When adding new features:

1. **Add implementation** in appropriate module (processor.py, api.py, or cli.py)
2. **Add tests** in corresponding test file
3. **Update API exports** in `__init__.py` if needed
4. **Update README.md** with usage examples
5. **Add docstrings** following Google style

Example docstring:
```python
def my_function(param1: int, param2: str) -> bool:
    """
    Brief description of function.

    More detailed description if needed.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Example:
        >>> my_function(42, "test")
        True
    """
    pass
```

## Testing Guidelines

### Test Coverage

- Aim for >90% test coverage
- Test both success and failure cases
- Include edge cases and boundary conditions
- Use fixtures for common test data

### Writing Tests

```python
def test_feature_name(fixture1, fixture2):
    """Test description."""
    # Arrange
    input_data = ...

    # Act
    result = function_under_test(input_data)

    # Assert
    assert result == expected_value
```

### Integration Tests

Mark integration tests (requiring network access) with:
```python
@pytest.mark.integration
def test_download_real_data():
    """Integration test requiring network."""
    pytest.skip("Requires network access")
    # Test implementation
```

## Performance Considerations

When making changes:

1. **Benchmark critical paths**: Use `time.time()` or `pytest-benchmark`
2. **Profile memory usage**: Ensure reasonable memory consumption
3. **Test with large datasets**: Verify scalability
4. **Document performance characteristics**: Update README benchmarks if needed

## Documentation

### Docstring Format

Use Google-style docstrings:

```python
def process_data(data: pd.DataFrame, compression: str = "zstd") -> Path:
    """
    Process data with specified compression.

    Args:
        data: Input DataFrame with tick data
        compression: Compression method (default: zstd)

    Returns:
        Path to output file

    Raises:
        ValueError: If data is empty or invalid

    Example:
        >>> df = pd.DataFrame(...)
        >>> output = process_data(df, compression="zstd")
    """
    pass
```

### README Updates

When adding features:
- Add usage examples
- Update feature list
- Document any breaking changes
- Update benchmark tables if relevant

## Questions?

If you have questions:

1. Check existing issues and discussions
2. Read the README and documentation
3. Open a GitHub issue with the `question` label

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
