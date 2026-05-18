# Baserow developer documentation

This site is the developer reference for working on Baserow. The full list
of docs is in the sidebar; this page is a curated entry point.

If you're trying to **install or self-host Baserow**, jump to
[Operations](#operations). If you're trying to **use** Baserow as a product,
the user guides are at [baserow.io/docs](https://baserow.io/docs) (different
site).

## Start here

New to the codebase? Read these in order. They build on each other.

1. [Introduction](technical/introduction.md) — what Baserow is technically.
2. [Systems overview](technical/systems-overview.md) — the map of subsystems.
3. [Architectural patterns](patterns/architecture.md) — view → service →
   action → handler → ORM.
4. [Registries](patterns/registries.md) — the extension pattern used
   everywhere.
5. [Baserow vs Django](patterns/baserow-vs-django.md) — the word overloads
   (field, table, model, application). The short page that prevents most
   confusion.
6. [Editions and licensing](technical/editions-and-licensing.md) — what's
   in the free edition (core + contrib) vs premium vs enterprise.

## Getting your environment running

* [Development environment](development/development-environment.md) —
  Docker vs local, which to pick.
* [Running locally](development/running-the-dev-env-locally.md) /
  [running with Docker](development/running-the-dev-env-with-docker.md).
* [Running tests](development/running-tests.md).
* [justfile reference](development/justfile.md) — every `just` recipe.
* [IntelliJ](development/intellij-setup.md) /
  [VS Code](development/vscode-setup.md) setup.
* [Debugging](development/debugging.md) — tools and how to use them.

## How we work

* [Engineering workflow](development/engineering-workflow.md) — issue → PR
  → review → merge.
* [Project conventions](development/conventions.md) — the "we do this here"
  rules: loguru, type hints, comments, locales, `just` recipes, commits.
  **Read this on your first day.**
* [Skills](development/skills-index.md) — reusable workflow recipes
  (`add-django-config-env-var`, `write-backend-unit-test`,
  `create-in-app-notification`, …). Use these instead of re-deriving.
* [Code quality](development/code-quality.md) — linters, formatters, CI.
* [Feature flags](development/feature-flags.md).

## Patterns and recipes

For the architectural map see [Architectural patterns](patterns/architecture.md).
For how to ship a new feature:

* [Creating a feature](patterns/creating-features.md) — end-to-end
  checklist.
* [Query patterns](patterns/queries.md) — `select_related`,
  `prefetch_related`, `specific_iterator`, bulk writes, N+1 avoidance.
* [Celery](technical/celery.md) — the async runtime: workers, queues, tasks, periodic, singleton.
* [Jobs](technical/jobs.md) — Celery wrapper for user-triggered work with progress + cancel.
* [Observability](patterns/observability.md) — logging and tracing.
* Smaller patterns: [forms](patterns/forms.md),
  [modals](patterns/modals.md), [context menus](patterns/context-menus.md),
  [dropdowns](patterns/dropdowns.md), [CRUD tables](patterns/crud-tables.md),
  [alerts and toasts](patterns/alerts-and-toasts.md),
  [frontend notifications](patterns/frontend-notifications.md),
  [emails](patterns/emails.md), [date and time](patterns/date-and-time.md),
  [row history from action](patterns/row_history_from_action.md), and
  [loading animations](patterns/loading-animations.md).

## System deep dives

The reference for each major subsystem. Read after the "Start here" path.

**Database plugin:**

* [Database plugin](technical/database-plugin.md) — entry point.
* [Field system](patterns/field-system.md) — central architectural concept.
* [Dynamic models](technical/dynamic-models.md) — runtime model generation.
* [Formulas](technical/formula-technical-guide.md) — materialised
  expressions, the AST, the dependency graph.
* [Table rows full-text search](technical/table-rows-search.md) —
  async tsvector indexing pipeline.
* [Workspace search](technical/workspace-search.md) — cross-type
  aggregation.

**Core systems:**

* [Action system](technical/action-system.md) and
  [undo / redo](technical/undo-redo-guide.md).
* [Permissions](technical/permissions-guide.md).
* [Trash system](technical/trash-system.md).
* [Notifications](technical/notification-system.md).
* [Serialization](technical/serialization-system.md) — export / import /
  snapshots / templates / duplication.
* [Caching](technical/caching.md).
* [WebSockets](technical/websockets.md).
* [PostgreSQL locks](technical/postgresql-locks.md) — isolation,
  `select_for_update`, deadlocks, snapshot reads.

## APIs

* [REST API](apis/rest-api.md).
* [WebSocket API](apis/web-socket-api.md).
* [Deprecations](apis/deprecations.md).

## Extending Baserow

The currently supported way to extend a self-hosted install:

* [Custom client scripts](plugins/custom-client-scripts.md) — inject
  JavaScript into every page via `BASEROW_EXTRA_CLIENT_SCRIPT_URLS`
  (enterprise feature). This is the recommended extension mechanism today.

### Legacy plugin system (pre-2.1)

The original plugin system is historical and does not work with current
Baserow. See [Plugin basics](plugins/introduction.md) for the full warning and
the supported alternative. The pages below remain for reference only.

* [Plugin basics](plugins/introduction.md) (legacy)
* [Plugin installation](plugins/installation.md) (legacy)
* [Boilerplate](plugins/boilerplate.md) (legacy)
* [Plugin creation](plugins/creation.md) (legacy)
* [Application type](plugins/application-type.md) (legacy)
* [View type](plugins/view-type.md) (legacy)
* [View filter type](plugins/view-filter-type.md) (legacy)
* [Field type](plugins/field-type.md) (legacy)
* [Field converter](plugins/field-converter.md) (legacy)

## Tutorials

User-facing how-tos.

* [Understanding Baserow formulas](tutorials/understanding-baserow-formulas.md).
* [Pre-filling forms](tutorials/prefill-forms.md).
* [Debugging connection issues](tutorials/debugging-connection-issues.md).

## Operations

Self-hosting, deploying, and running Baserow in production.

* [Configuration reference](installation/configuration.md) — every env var.
* [Supported runtimes](installation/supported.md).
* [Install with Docker](installation/install-with-docker.md) — the most
  common path.
* [Install with Docker Compose](installation/install-with-docker-compose.md).
* [Install with Helm](installation/install-with-helm.md) /
  [K8s](installation/install-with-k8s.md).
* [Monitoring](installation/monitoring.md) +
  [metrics and logs](development/metrics-and-logs.md).
* [Backup and restore](runbooks/back-up-and-restore-baserow.md).
* [SSO / SAML](development/sso-saml.md).
* [Read replicas](development/read-replicas.md).
* [Secure file serve](installation/secure-file-serve.md).
* [Embeddings server](development/embeddings-server.md),
  [AI assistant setup](installation/ai-assistant.md),
  [MCP server](development/mcp-server.md).

The sidebar has the full list of platform-specific install guides (AWS,
Heroku, Render, Railway, Cloudron, Digital Ocean, Ubuntu, behind Nginx /
Apache / Traefik, third-party providers).

## Decisions (ADRs)

* [Decision index and backlog](decisions/index.md).

## Other

* [External resources](other/external-resources.md).
