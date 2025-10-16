# Makefile for exness-data-preprocess
#
# Introspection commands for module statistics and project metrics

.PHONY: module-stats module-complexity module-deps clean test help

# Show current line counts for all modules
module-stats:
	@echo "Module Statistics (current line counts)"
	@echo "========================================"
	@cd src/exness_data_preprocess && \
	for f in *.py; do \
		echo "$$f: $$(wc -l < "$$f") lines"; \
	done | sort
	@echo ""
	@echo "Note: Line counts include comments, docstrings, and blank lines"

# Show module complexity using radon (requires: pip install radon)
module-complexity:
	@echo "Module Complexity Analysis"
	@echo "=========================="
	@which radon > /dev/null 2>&1 || (echo "Error: radon not installed. Run: uv pip install radon" && exit 1)
	@radon cc src/exness_data_preprocess/*.py -s -a
	@echo ""
	@echo "Complexity Ratings: A=simple, B=low, C=moderate, D=high, E=very high, F=extremely high"

# Show module dependencies using pipdeptree (requires: pip install pipdeptree)
module-deps:
	@echo "Module Dependencies"
	@echo "==================="
	@which pipdeptree > /dev/null 2>&1 || (echo "Error: pipdeptree not installed. Run: uv pip install pipdeptree" && exit 1)
	@pipdeptree --packages exness-data-preprocess

# Run test suite
test:
	@uv run pytest -v --tb=short

# Run test suite with coverage
test-cov:
	@uv run pytest --cov=exness_data_preprocess --cov-report=html --cov-report=term

# Clean build artifacts
clean:
	@rm -rf dist/ build/ *.egg-info
	@rm -rf .pytest_cache .ruff_cache .mypy_cache
	@rm -rf htmlcov/
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Cleaned build artifacts"

# Show help
help:
	@echo "Available commands:"
	@echo ""
	@echo "  make module-stats       Show current line counts for all modules"
	@echo "  make module-complexity  Show cyclomatic complexity analysis (requires radon)"
	@echo "  make module-deps        Show package dependency tree (requires pipdeptree)"
	@echo "  make test               Run test suite"
	@echo "  make test-cov           Run test suite with coverage report"
	@echo "  make clean              Remove build artifacts and caches"
	@echo "  make help               Show this help message"
	@echo ""
	@echo "Documentation: See CLAUDE.md for architecture and design patterns"
