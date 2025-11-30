# Backend Development Guide

This guide helps AI assistants understand the Baserow backend codebase.

## Quick Reference

```bash
# All commands use just (run from backend/ or use `just b` from root)
just init              # Initialize venv, install deps
just test              # Run tests
just test -n=auto      # Run tests in parallel
just lint              # Run all linters
just fix               # Auto-fix code style
just run-dev-server    # Start Django dev server
just run-dev-celery    # Start all Celery workers
just shell             # Django shell with SQL logging
just m <cmd>           # Run manage.py commands
```

## Code Organization

```
backend/
├── src/baserow/
│   ├── core/              # Core functionality (users, workspaces, jobs, etc.)
│   ├── contrib/           # Application modules
│   │   ├── database/      # Database application (tables, fields, views, rows)
│   │   ├── builder/       # Page builder application
│   │   ├── automation/    # Workflow automation
│   │   ├── dashboard/     # Dashboard widgets
│   │   └── integrations/  # External service integrations
│   ├── api/               # REST API (DRF views, serializers, urls)
│   ├── ws/                # WebSocket consumers
│   ├── config/            # Django settings
│   └── test_utils/        # Shared test fixtures and helpers
├── tests/                 # Test files (mirrors src/ structure)
├── justfile               # Development commands
└── pyproject.toml         # Dependencies and project config
```

### Premium & Enterprise

Additional features are in separate packages:

- `premium/backend/` - Premium features (row comments, row coloring, etc.)
- `enterprise/backend/` - Enterprise features (SSO, audit log, etc.)

These are installed as editable dependencies via `uv.sources` in pyproject.toml.

## Architecture Patterns

### Registry Pattern

Baserow uses registries to manage pluggable components:

```python
from baserow.contrib.database.fields.registries import field_type_registry

# Register a new field type
field_type_registry.register(MyFieldType())

# Get a field type
field_type = field_type_registry.get("text")
```

Common registries:
- `field_type_registry` - Field types (text, number, date, etc.)
- `view_type_registry` - View types (grid, gallery, form, etc.)
- `application_type_registry` - Application types (database, builder, etc.)

### Handler Pattern

Business logic is encapsulated in handler classes:

```python
from baserow.contrib.database.rows.handler import RowHandler

handler = RowHandler()
row = handler.create_row(user, table, values)
```

### Signal Pattern

Cross-cutting concerns use Django signals:

```python
from baserow.contrib.database.rows.signals import row_created

@receiver(row_created)
def on_row_created(sender, row, user, **kwargs):
    # React to row creation
    pass
```

## Testing

```bash
# Run specific test file
just test tests/baserow/contrib/database/test_table_handler.py

# Run specific test
just test tests/baserow/contrib/database/test_table_handler.py::test_create_table

# Run tests matching pattern
just test -k "test_create"

# Run with coverage
just test-coverage

# Fast tests with ramdisk DB (2-5x faster, run from project root)
just test-db
DATABASE_URL=postgres://baserow:baserow@localhost:5433/baserow just b test
```

### Test Fixtures

Use `data_fixture` for creating test data:

```python
@pytest.fixture
def data_fixture():
    return Fixtures()

def test_something(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
```

## Environment

### Local Development

Environment variables are loaded from `.env.local` (project root):

```bash
# Load manually
source ../.env.local

# Or use direnv (automatic)
direnv allow
```

Key variables:
- `DATABASE_URL` - PostgreSQL connection
- `REDIS_URL` - Redis connection
- `DJANGO_SETTINGS_MODULE` - Settings module (default: `baserow.config.settings.dev`)

### Running Services

For local development, you need PostgreSQL and Redis:

```bash
# Option 1: Use Docker for services only
just dc-dev up -d db redis

# Option 2: Run everything in Docker
just dc-dev up -d
```

## Common Tasks

### Adding a New Field Type

1. Create field type class in `contrib/database/fields/`
2. Register in `contrib/database/fields/registries.py`
3. Add serializer in `api/database/fields/`
4. Add tests in `tests/baserow/contrib/database/fields/`

### Adding an API Endpoint

1. Create view in `api/<module>/views.py`
2. Add serializers in `api/<module>/serializers.py`
3. Register URLs in `api/<module>/urls.py`
4. Add tests in `tests/baserow/api/<module>/`

### Database Migrations

```bash
just m makemigrations          # Create migrations
just m migrate                 # Apply migrations
just m makemigrations --check  # Check for missing migrations (used in CI)
```
