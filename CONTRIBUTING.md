# Contributing to manage-agenda

Thank you for your interest in contributing to manage-agenda! This document provides guidelines and instructions for contributing.

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/fernand0/manage-agenda.git
   cd manage-agenda
   ```

2. **Install dependencies**
   ```bash
   # Using uv (recommended)
   uv sync --dev
   
   # Or using pip
   pip install -e '.[dev]'
   ```

3. **Install pre-commit hooks**
   ```bash
   pre-commit install
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

## Code Quality Standards

### Formatting
- **Black**: Code formatter (line length: 100)
- **isort**: Import sorting
- Run: `black . && isort .`

### Linting
- **Ruff**: Fast Python linter
- Run: `ruff check . --fix`

### Security
- **Bandit**: Security issue scanner
- Run: `bandit -r manage_agenda/`

### Pre-commit
All checks run automatically on commit. To run manually:
```bash
pre-commit run --all-files
```

## Testing

### Running Tests
```bash
# All tests
pytest

# With coverage
pytest --cov=manage_agenda --cov-report=html

# Specific test file
pytest tests/test_utils.py

# Specific test
pytest tests/test_utils.py::test_function_name
```

### Writing Tests
- Place tests in the `tests/` directory
- Name test files `test_*.py`
- Name test functions `test_*`
- Use fixtures for common setup
- Mock external API calls

## Making Changes

### Branch Naming
- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation only
- `refactor/description` - Code refactoring

### Commit Messages
Follow conventional commits:
```
type(scope): description

[optional body]

[optional footer]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Example:
```
feat(calendar): add support for recurring events

- Added recurrence pattern parsing
- Updated event validation
- Added tests for recurring events

Closes #123
```

### Pull Request Process

1. **Update your branch**
   ```bash
   git checkout devel
   git pull origin devel
   git checkout your-branch
   git rebase devel
   ```

2. **Run all checks**
   ```bash
   pre-commit run --all-files
   pytest
   ```

3. **Create PR**
   - Target the `devel` branch
   - Provide clear description
   - Reference related issues
   - Add tests for new features
   - Update documentation if needed

## Code Style Guidelines

### Python Code
- Follow PEP 8 (enforced by Black/Ruff)
- Maximum line length: 100 characters
- Use type hints for function signatures
- Document public functions with docstrings

### Docstrings
Use Google style:
```python
def function_name(param1: str, param2: int) -> bool:
    """Brief description.
    
    Longer description if needed.
    
    Args:
        param1: Description of param1.
        param2: Description of param2.
        
    Returns:
        Description of return value.
        
    Raises:
        ValueError: When invalid input is provided.
    """
    pass
```

### Error Handling
- Use custom exceptions from `exceptions.py`
- Log errors appropriately
- Provide helpful error messages
- Don't catch generic `Exception` unless necessary

## Project Structure

```
manage-agenda/
├── manage_agenda/          # Main package
│   ├── __init__.py
│   ├── cli.py             # CLI commands
│   ├── config.py          # Configuration management
│   ├── exceptions.py      # Custom exceptions
│   ├── utils.py           # Main utilities
│   ├── utils_base.py      # Base utilities
│   ├── utils_llm.py       # LLM integration
│   └── utils_web.py       # Web scraping
├── tests/                 # Test suite
├── .env.example          # Environment template
├── .pre-commit-config.yaml
├── pyproject.toml        # Project configuration
└── README.md
```

## Getting Help

- Open an issue for bugs or feature requests
- Check existing issues and PRs first
- For questions, use GitHub Discussions

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.
