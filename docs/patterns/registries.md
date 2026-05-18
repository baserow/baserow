# Registries

Registries are the single most common pattern in the Baserow codebase. Fields,
views, view filters, applications, actions, jobs, formulas, permission managers,
trash items, notification types, integrations, and webhook events are all built on
them. If you understand registries, you understand the shape of most of the code.

## What a registry is

A registry is a collection of all the concrete implementations of a base class,
keyed by a unique string `type`. We use registries to:

- Look up an implementation given a type string (e.g. "what's the field type for
  `text`?").
- Iterate over all implementations (e.g. "give me every sortable field type").
- Provide an extension point so plugins (including premium and enterprise) can add
  new implementations without modifying core code.

## A simplified example

The real codebase wraps registries in helper classes (see below), but the underlying
idea is just a dictionary of instances:

```python
import abc

# 1. The base class — defines the interface every concrete type must implement.
class FieldType(abc.ABC):
    type: str
    is_sortable: bool = False

    @abc.abstractmethod
    def prepare_value_for_db(self, value): ...

# 2. Two concrete implementations, each with a unique `type`.
class TextFieldType(FieldType):
    type = "text"
    is_sortable = True

    def prepare_value_for_db(self, value):
        if not isinstance(value, str):
            raise ValueError()
        return value

class NumberFieldType(FieldType):
    type = "number"
    is_sortable = True

    def prepare_value_for_db(self, value):
        if not isinstance(value, int):
            raise ValueError()
        return value

# 3. The "registry" — in real code this is wrapped in a Registry class, but it is
#    fundamentally a dict of instances keyed by `type`.
field_type_registry = {
    TextFieldType.type: TextFieldType(),
    NumberFieldType.type: NumberFieldType(),
}

# 4. Two common usages: look up by type, and filter across all types.
def validate_new_cell_value(field_type: str, cell_value):
    return field_type_registry[field_type].prepare_value_for_db(cell_value)

def get_all_sortable_field_types():
    return [ft for ft in field_type_registry.values() if ft.is_sortable]
```

The concrete instances are stateless singletons. They behave like plain functions
grouped onto a class — having them as instances rather than module-level functions
is what lets us iterate, filter and look them up uniformly.

## The real implementation

The base classes and registry helpers live in
`backend/src/baserow/core/registry.py`:

- `Instance` — the abstract base every registered class extends. Owns the `type`
  property and lifecycle hooks (`after_register`, `before_unregister`).
- `Registry` — the dict wrapper. Provides `register`, `unregister`, `get`,
  `get_all`, and dispatches the lifecycle hooks.
- Several mixins (`ModelInstanceMixin`, `CustomFieldsInstanceMixin`,
  `APIUrlsInstanceMixin`, `MapAPIExceptionsInstanceMixin`, …) add common behaviour
  for registries whose entries need a related Django model, custom serializer
  fields, extra API URLs, or exception mapping.

A real registry looks like:

```python
from baserow.core.registry import Registry, ModelInstanceMixin, Instance

class FieldType(ModelInstanceMixin, Instance):
    ...

class FieldTypeRegistry(Registry):
    name = "field"

field_type_registry = FieldTypeRegistry()
```

Registration happens at app-ready time, typically from each app's `apps.py`:

```python
def ready(self):
    from .registries import field_type_registry
    from .field_types import TextFieldType, NumberFieldType

    field_type_registry.register(TextFieldType())
    field_type_registry.register(NumberFieldType())
```

## A non-exhaustive tour of the registries

> **Source of truth:** every registry lives in a `registries.py` file under
> `backend/src/baserow/`. To get the current full list, run
> `find backend/src/baserow -name registries.py` (and the same under
> `premium/` and `enterprise/`). The tour below is a guided sample of the
> most-touched ones and will drift over time — trust the file system, not
> this page.

In `backend/src/baserow/core/`:

- `registries.py` — `application_type_registry`, `plugin_registry`,
  `permission_manager_type_registry`, `object_scope_type_registry`,
  `operation_type_registry`, `email_context_registry`,
  `subject_type_registry`, `auth_provider_type_registry`.
- `action/registries.py` — `action_type_registry`, `action_scope_registry`.
- `jobs/registries.py` — `job_type_registry`.
- `notifications/registries.py` — `notification_type_registry`.
- `trash/registries.py` — `trash_item_type_registry`.
- Plus `search/`, `services/`, `integrations/`, `user_sources/`, `formula/`,
  `mcp/`, `captcha/`, `workflow_actions/` — each with its own `registries.py`.

In `backend/src/baserow/contrib/database/`:

- `fields/registries.py` — `field_type_registry`,
  `field_converter_registry`, `field_aggregation_registry`.
- `views/registries.py` — `view_type_registry`, `view_filter_type_registry`,
  `view_aggregation_type_registry`, `decorator_value_provider_type_registry`, …
- Plus `webhooks/`, `data_sync/`, `export/`, `airtable/` — each with its own
  `registries.py`.

In `backend/src/baserow/ws/` and `backend/src/baserow/api/`:

- `ws/registries.py` — `page_registry` for the websocket subscription model.
- `api/registries.py` — `api_exception_registry` for exception serialisation.

## Adding a new type

The most common reason to touch a registry is to register a new type from a
feature, contrib module, premium or enterprise. The pattern is always the
same: subclass the base, give it a unique `type` string, implement the
abstract methods, and register the instance from `apps.py` `ready()` (or the
frontend module's `plugin.js` for frontend registries).

For concrete examples, use current docs such as [Field system](field-system.md),
[View filters](view-filters.md), [Job types](jobtypes.md), and
[Frontend registries](frontend-registries.md). The old pages under
[`docs/plugins/`](../plugins/introduction.md) are historical only.

## When to use a registry yourself

If you find yourself writing `if field_type == "text": ... elif field_type ==
"number": ...` in business logic, that branching belongs on the field type
subclass, not at the call site. The registry exists so that adding a new field type
is a single new class plus a registration — not a sweep through every `if/elif` in
the codebase.
