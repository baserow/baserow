# Baserow Project Justfile
# Root justfile that delegates to component-specific justfiles

# Default recipe - show help
default:
    @just --list

# =============================================================================
# Backend
# =============================================================================

# Run any backend command (e.g., just backend init, just backend test)
[doc("Run backend command: just backend <cmd> or just b <cmd>")]
backend *args:
    @just --justfile backend/justfile {{ args }}

# Shortcut alias for backend
alias b := backend

# Shortcut aliases for common backend commands
[doc("Initialize backend: create venv, install deps")]
init-backend:
    @just backend init

[doc("Run backend dev server")]
run-backend:
    @just backend run-dev

[doc("Run backend tests")]
test-backend:
    @just backend test

[doc("Run backend linter")]
lint-backend:
    @just backend lint

[doc("Fix backend code style")]
fix-backend:
    @just backend fix

# =============================================================================
# Frontend (placeholder for future)
# =============================================================================

# frontend *args:
#     @just --justfile web-frontend/justfile {{ args }}

# =============================================================================
# Full Stack
# =============================================================================

# Initialize everything
init: init-backend
    @echo ""
    @echo "Project initialized!"
    @echo "Run 'just run-backend' to start the backend dev server"

# Run all linters
lint: lint-backend
    @echo "All linting complete!"

# Run all tests
test: test-backend
    @echo "All tests complete!"

# Fix all code style
fix: fix-backend
    @echo "All code style fixes complete!"
