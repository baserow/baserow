---
name: baserow-registry
description: Explain, create, update, or use Baserow registries across backend and frontend code, including Instance/Registry patterns, registration points, model-backed type registries, serializer/API URL/import-export helpers, and the registry mixins in baserow.core.registry.
---

# Baserow Registry

Use this skill when explaining or changing Baserow registries, especially:

- backend registries based on `baserow.core.registry.Instance` and `Registry`
- model-backed typed objects such as fields, views, elements, services, widgets, domains, auth providers, workflow actions, and automation nodes
- frontend registries based on `web-frontend/modules/core/registry.js`
- registry mixins and what behavior each one adds

## First Step

Inspect the closest existing registry before editing. Useful patterns:

- Core backend implementation: `backend/src/baserow/core/registry.py`
- Field types: `backend/src/baserow/contrib/database/fields/registries.py`
- Builder elements: `backend/src/baserow/contrib/builder/elements/registries.py`
- Services: `backend/src/baserow/core/services/registries.py`
- Frontend registry: `web-frontend/modules/core/registry.js`
- Registrations usually live in an app `apps.py`, module `plugin.js`, or package `config.py`

Useful searches:

- `rg -n "class .*Registry|_registry = .*Registry|\\.register\\(" backend/src premium/backend enterprise/backend`
- `rg -n "register\\(new .*Type|registerNamespace|getOrderedList|getAll\\(" web-frontend premium/web-frontend enterprise/web-frontend`
- `rg -n "ModelRegistryMixin|CustomFieldsRegistryMixin|APIUrlsRegistryMixin|EasyImportExportMixin" backend/src`

## Backend Registry Shape

A simple backend registry has an `Instance` subclass, a `Registry` subclass with a stable `name`, and a singleton registry object:

```python
from baserow.core.registry import Instance, Registry


class ExampleType(Instance):
    type = "example"


class ExampleTypeRegistry(Registry[ExampleType]):
    name = "example_type"


example_type_registry = ExampleTypeRegistry()
```

Baserow convention is that backend registry instance classes end with `Type`,
registry classes end with `TypeRegistry`, and singleton variables end with
`_type_registry`. Put concrete implementations in a `*_types.py` module when
they live outside `registries.py` (for example `field_types.py` or
`service_types.py`), and keep the registry singleton in `registries.py`.

Register instantiated types at application startup:

```python
example_type_registry.register(ExampleType())
```

Core operations:

- `registry.register(instance)` adds an instance and calls `instance.after_register()`.
- `registry.unregister(instance_or_type)` removes it and calls `before_unregister()`.
- `registry.get(type_name)` returns the instance or raises the registry's does-not-exist exception.
- `registry.get_all()` returns registered instances.
- `registry.get_types()` returns registered type strings.
- `instance.compat_type` can map an old type name to a renamed type.

Use custom exception classes on the registry when callers need domain-specific errors:

```python
class ExampleTypeRegistry(Registry[ExampleType]):
    name = "example_type"
    does_not_exist_exception_class = ExampleTypeDoesNotExist
    already_registered_exception_class = ExampleTypeAlreadyRegistered
```

## Model-Backed Type Registries

Use `ModelInstanceMixin` on the type and `ModelRegistryMixin` on the registry when each registered type owns a Django model subclass:

```python
class ExampleType(ModelInstanceMixin[Example], Instance):
    type = "example"
    model_class = Example


class ExampleTypeRegistry(
    ModelRegistryMixin[Example, ExampleType],
    Registry[ExampleType],
):
    name = "example_type"
```

This enables:

- `registry.get_by_model(model_or_instance)`
- `registry.get_for_class(model_class)`
- `registry.get_model_names()`
- model polymorphism through `.specific`, `.specific_class`, and `WithRegistry`

For model classes participating in a registry, follow existing model patterns with `WithRegistry` and implement `get_type_registry()` when needed.

## Custom Serializers

Use `CustomFieldsInstanceMixin` on the type and `CustomFieldsRegistryMixin` on the registry when each type contributes model fields to generated serializers.

Type-level properties:

- `allowed_fields`: fields accepted during create/update.
- `serializer_field_names`: fields exposed in generated serializers.
- `request_serializer_field_names`: request-specific field list.
- `serializer_field_overrides`: DRF field overrides.
- `request_serializer_field_overrides`: request-specific overrides.
- `serializer_mixins`: serializer mixins or lazy functions returning mixins.
- `request_serializer_mixins`: request-specific mixins.
- `serializer_field_extra_kwargs`: extra DRF `Meta.extra_kwargs`.
- `serializer_extra_args`: extra serializer arguments for local conventions.

Use `PublicCustomFieldsInstanceMixin` when public APIs must expose a narrower field set than internal APIs. Pass `extra_params={"public": True}` to select public fields, overrides, and mixins.

## Import And Export

Use `ImportExportMixin` when export/import is custom or not model-shaped. Implement:

- `export_serialized(instance)`
- `import_serialized(parent, serialized_values, id_mapping, ...)`

Use `EasyImportExportMixin` for model-backed types with direct property serialization. Define:

- `SerializedDict`: a `TypedDict` describing exported properties.
- `parent_property_name`: the parent relation to set during import.
- `id_mapping_name`: optional mapping key to populate.
- `model_class`: the model class to create.
- `sensitive_fields`: fields omitted when `exclude_sensitive_data` is enabled.

Override `serialize_property`, `deserialize_property`, or `create_instance_from_serialized` for file handling, ID remapping, compatibility, or custom creation.

## API URLs And Exceptions

Use `APIUrlsInstanceMixin` on instances that contribute API routes and `APIUrlsRegistryMixin` on the registry. Include `registry.api_urls` in the owning URL module.

Use `MapAPIExceptionsInstanceMixin` when type-specific domain exceptions should map to API errors:

```python
class ExampleType(MapAPIExceptionsInstanceMixin, Instance):
    api_exceptions_map = {
        ExampleError: ERROR_EXAMPLE,
    }

with example_type.map_api_exceptions():
    ...
```

## Formula-Aware Types

Use `InstanceWithFormulaMixin` or a domain-specific subclass such as builder formula mixins when a type owns formula strings that need import rewriting. Set `simple_formula_fields` for straightforward model fields, or override `formula_generator()` for formulas inside JSON fields or nested structures.

## Frontend Registry Shape

Frontend registry code uses `Registerable` and `Registry` from `web-frontend/modules/core/registry.js`.

Define a registerable type:

```javascript
import { Registerable } from '@baserow/modules/core/registry'

export class ExampleType extends Registerable {
  static getType() {
    return 'example'
  }

  getOrder() {
    return 10
  }
}
```

Register it in a plugin after the namespace exists:

```javascript
app.$registry.register('example', new ExampleType({ app }))
```

Common frontend operations:

- `registerNamespace(namespace)`
- `register(namespace, object)`
- `unregister(namespace, type)`
- `get(namespace, type)`
- `getAll(namespace)`
- `getList(namespace)`
- `getOrderedList(namespace)`
- `exists(namespace, type)`

The frontend `getType()` should match the backend `type` when both sides describe the same feature.

## Mixin Reference

Backend mixins in `baserow.core.registry`:

- `ModelInstanceMixin`: attaches `model_class` to an instance and adds content-type/object helpers. Pair with `ModelRegistryMixin`.
- `ModelRegistryMixin`: finds registered types by model class or model instance. Use for polymorphic/model-backed registries.
- `CustomFieldsInstanceMixin`: lets a type define allowed fields, serializer fields, overrides, mixins, and queryset enhancement.
- `PublicCustomFieldsInstanceMixin`: extends custom fields with public/private serializer variants selected by `extra_params["public"]`.
- `CustomFieldsRegistryMixin`: delegates serializer generation to the registered type selected by a model instance.
- `APIUrlsInstanceMixin`: lets a registered type return extra Django URL patterns.
- `APIUrlsRegistryMixin`: aggregates `get_api_urls()` from all registered types.
- `MapAPIExceptionsInstanceMixin`: maps type-specific exceptions to API errors with `map_api_exceptions()`.
- `ImportExportMixin`: abstract manual import/export contract.
- `EasyImportExportMixin`: generic model import/export implementation using a `TypedDict` property list and import ID mappings.
- `InstanceWithFormulaMixin`: iterates and rewrites formula fields during import/export workflows.

Related non-registry mixin:

- `baserow.core.mixins.WithRegistry`: placed on model classes so model instances can resolve their registry/type with local conventions.

Frontend registry base classes:

- `Registerable`: base class for frontend objects that can be registered; provides `getType()`, `type`, `getOrder()`, and `$t()`.
- `Registry`: namespace-based frontend registry for `Registerable` instances.

## Checklist For New Or Updated Registries

1. Choose the nearest existing registry as the pattern.
2. Define or update the instance/type class and required stable `type`.
3. Add only the mixins needed by the behavior.
4. Define or update the registry class with a stable `name`.
5. Register instances during app/plugin startup.
6. Wire API URLs, serializers, import/export, formulas, or model `WithRegistry` only when the feature needs them.
7. Add focused tests around registration, lookup, serializer generation, import/export, or frontend registry behavior based on the touched surface.
