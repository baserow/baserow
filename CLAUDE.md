# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Baserow is an open-source no-code platform and Airtable alternative built with Django (backend) and Vue.js/Nuxt.js (frontend). It provides databases, applications, automations, and dashboards in a self-hostable environment.

**Tech Stack:**
- Backend: Python 3.11+, Django, PostgreSQL, Redis, Celery
- Frontend: Node 24.x, Vue.js 2, Nuxt 2, SCSS with BEM
- Testing: pytest (backend), Jest (frontend), Playwright (e2e)
- Container orchestration: Docker Compose

## Repository Structure

```
baserow/
├── backend/           # Django backend application
│   ├── src/baserow/
│   │   ├── api/      # REST API endpoints
│   │   ├── core/     # Core functionality (registries, handlers, models)
│   │   └── contrib/  # Main features (database, builder, automation, dashboard, integrations)
│   └── requirements/ # Python dependencies
├── web-frontend/      # Nuxt.js frontend application
│   └── modules/      # Feature modules (core, database, builder, automation, dashboard, integrations)
├── premium/          # Premium features (backend + web-frontend)
├── enterprise/       # Enterprise features (backend + web-frontend)
├── e2e-tests/        # Playwright end-to-end tests
└── plugin-boilerplate/ # Plugin development template
```

## Development Environment

### Quick Start

```bash
# Start dev environment (uses docker-compose with hot reloading)
./dev.sh --build

# Access at http://localhost:3000 (frontend) and http://localhost:8000 (backend API)
```

The `./dev.sh` script wraps docker-compose with correct environment variables. Run `./dev.sh help` for options.

### Working Without Docker

**Backend:**
```bash
cd backend
make install          # Create venv and install all deps (OSS + premium + enterprise)
make install-oss      # Install only OSS version
make run-dev          # Run Django dev server
```

**Frontend:**
```bash
cd web-frontend
yarn install
yarn dev             # Run Nuxt dev server
```

## Common Commands

### Building & Running

```bash
# Root level - Docker orchestration
make docker-build         # Build all containers
make docker-start         # Start dev containers
make docker-stop          # Stop containers
make docker-status        # Show container status
make docker-backend-shell # Shell into backend container
make docker-frontend-shell # Shell into frontend container
```

### Testing

**Backend (pytest):**
```bash
cd backend
make test                    # Run all tests (core + premium + enterprise)
make test-parallel           # Run tests in parallel (10 workers)
make test-coverage           # Run with coverage report
make test-builder            # Test only builder module
make test-automation         # Test only automation module

# Run specific test file
source ../venv/bin/activate
pytest tests/path/to/test_file.py

# Run specific test function
pytest tests/path/to/test_file.py::test_function_name

# Run tests with specific marker
pytest -m field_formula      # Run only formula field tests
```

**Frontend (Jest):**
```bash
cd web-frontend
yarn test                    # Run all tests (core + premium + enterprise)
yarn test-core               # Run core tests only
yarn test-premium            # Run premium tests only
yarn test-enterprise         # Run enterprise tests only
yarn run jest path/to/test   # Run specific test file
yarn run jest --updateSnapshot # Update snapshots
```

**E2E Tests (Playwright):**
```bash
cd e2e-tests
yarn test                    # Run all e2e tests
yarn test-ui                 # Run with Playwright UI
yarn test-fast-only          # Run only @fast tagged tests
yarn test-builder            # Run only builder tests
yarn test-automation         # Run only automation tests
yarn codegen                 # Generate test code interactively
```

### Linting & Formatting

**Backend:**
```bash
cd backend
make lint                    # Check Python code (flake8, black, isort, bandit)
make lint-fix                # Auto-fix Python code
make format                  # Run black formatter
make sort                    # Sort imports with isort
```

**Frontend:**
```bash
cd web-frontend
yarn lint                    # Check JS/Vue code (eslint + stylelint)
yarn fix                     # Auto-fix JS/Vue/SCSS code
yarn eslint                  # Run eslint only
yarn stylelint               # Run stylelint only
```

**Root level:**
```bash
make lint                    # Run lint in both backend and frontend
make lint-fix                # Auto-fix in both backend and frontend
```

### Database & Migrations

```bash
# Inside backend container or with activated venv
cd backend
source ../venv/bin/activate
baserow migrate              # Run migrations
baserow makemigrations       # Create new migrations
baserow createsuperuser      # Create admin user
```

### Changelog

```bash
make changelog               # Create new changelog entry (uses changelog/add script)
```

## Architecture Concepts

### Registry Pattern

Baserow uses a registry pattern extensively for extensibility. Key registries are in `backend/src/baserow/core/registries.py`:

- **ApplicationTypeRegistry**: Register new application types
- **FieldTypeRegistry**: Register new database field types
- **ViewTypeRegistry**: Register new view types
- **ActionTypeRegistry**: Register undo/redo actions
- **PluginRegistry**: Register plugins
- **IntegrationTypeRegistry**: Register external integrations

To add a new type, create a class inheriting from the base type and register it in the appropriate registry during app initialization.

### Handler Pattern

Business logic is organized into "handlers" (services) in `backend/src/baserow/core/handler.py` and feature-specific handlers (e.g., `contrib/database/handler.py`). Handlers contain methods for CRUD operations and complex business logic, keeping views/API endpoints thin.

### Action System (Undo/Redo)

Baserow has a comprehensive undo/redo system. Most state-changing operations should be wrapped in Action classes (see `backend/src/baserow/core/actions.py` and feature-specific actions). Actions track changes for undo/redo and maintain audit history.

### Frontend Modules

Frontend code is organized into Nuxt modules under `web-frontend/modules/`:

- **core**: Base components, mixins, store, authentication, jobs
- **database**: Tables, fields, views, filters, sorts
- **builder**: Application builder UI
- **automation**: Workflow automation
- **dashboard**: Dashboard components
- **integrations**: External service integrations

Each module contains: `components/`, `store/`, `pages/`, `mixins/`, `assets/scss/`.

### Plugin System

Baserow supports plugins that can extend both backend and frontend. See `docs/plugins/introduction.md`. Plugins can:
- Add new field types, view types, formula functions
- Add pages and components
- Integrate with 3rd party APIs
- Install custom dependencies

Use `plugin-boilerplate/` as a template for creating plugins.

## Code Quality Standards

### Backend (Python)

- Follow PEP 8 (enforced by flake8)
- Use black formatter (line length: 88)
- Use isort for import sorting
- Write unit tests for all new functionality
- Use reStructuredText for docstrings
- Migrations must be reviewed carefully

### Frontend (JavaScript/Vue)

- Follow eslint:recommended rules
- Use BEM methodology for SCSS
- Write Jest tests for complex components and store modules
- Component names must be multi-word (Vue style guide)
- Use composition API patterns where possible

### Commit Conventions

- Generate changelog entries for all user-facing changes
- Follow existing commit message patterns
- Squash commits when merging (typically done by maintainers)

## Important Files

- `backend/src/baserow/config/settings/`: Django settings (dev.py, test.py, base.py)
- `backend/src/baserow/core/registries.py`: Central registry definitions
- `web-frontend/config/nuxt.config.js`: Nuxt configuration
- `docker-compose.dev.yml`: Development docker setup
- `.gitlab-ci.yml`: CI/CD pipeline definition
- `Makefile`, `backend/Makefile`, `web-frontend/Makefile`: Build automation

## Testing Markers

Backend tests use pytest markers for categorization (see `backend/pytest.ini`):
- `@pytest.mark.field_*`: Field type tests
- `@pytest.mark.view_*`: View type tests
- `@pytest.mark.undo_redo`: Undo/redo functionality
- `@pytest.mark.disabled_in_ci`: Skip in CI
- `@pytest.mark.once_per_day_in_ci`: Run daily only

## Running Single Components

### Backend API Only
```bash
make docker-backend-shell
# Inside container:
baserow runserver 0.0.0.0:8000
```

### Frontend Only
```bash
make docker-frontend-shell
# Inside container:
yarn dev
```

### Background Workers (Celery)
```bash
make docker-backend-shell
# Inside container:
celery -A baserow worker -l INFO
```

## Database Schema

- Main models: `backend/src/baserow/core/models.py`
- Database models: `backend/src/baserow/contrib/database/models.py`
- Builder models: `backend/src/baserow/contrib/builder/models.py`
- Migrations: `backend/src/baserow/*/migrations/`

Tables are dynamically generated based on Database model definitions. Field types determine column types through the FieldType registry.

## Configuration via Environment Variables

Key environment variables (see `.env.example` and `.env.dev.example`):
- `DATABASE_URL`: PostgreSQL connection
- `REDIS_URL`: Redis connection
- `SECRET_KEY`: Django secret key
- `BASEROW_JWT_SIGNING_KEY`: JWT signing key
- `FEATURE_FLAGS`: Comma-separated feature flags
- `BASEROW_ENABLE_OTEL`: OpenTelemetry tracing

## Git Workflow

- Main branch: `develop` (default development branch)
- Create branches from `develop`
- Set git blame to ignore formatting commits: `git config blame.ignoreRevsFile .git-blame-ignore-revs`

## Performance Notes

- Backend uses Celery for background tasks (exports, imports, snapshots)
- Frontend uses Nuxt.js SSR capabilities sparingly (mostly SPA mode)
- Database queries use select_related/prefetch_related extensively
- Redis caching via django-redis
- WebSocket support via Django Channels for real-time updates
