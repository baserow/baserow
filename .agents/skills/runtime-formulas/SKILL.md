---
name: runtime-formulas
description: Explain, debug, or extend Baserow runtime formulas, including FormulaField/JSONFormulaField storage, FormulaSerializerField validation, runtime formula functions, backend and frontend data providers, formula context dispatch data, import/export path rewriting, and tests.
---

# Runtime Formulas

Use this skill when a task involves runtime formulas in the Application Builder,
Automation, or another non-database-field surface. This includes:

- Explaining how runtime formulas are stored, validated, and resolved.
- Adding a formula-backed model field or serializer field.
- Implementing a new data provider.
- Changing the formula input data explorer.
- Adding a runtime formula function.
- Fixing formula import/export, duplication, or path migration bugs.
- Debugging formulas that use `get("provider.path")`.

Runtime formulas are different from database formula fields. They use the shared
formula parser and runtime functions, but their data comes from application
context providers instead of table rows.

## Mental Model

Runtime formula resolution has four main pieces:

1. The formula value is stored as a `BaserowFormulaObject` with `formula`, `mode`,
   and `version`.
2. API serializers use `FormulaSerializerField` to normalize and validate formula
   objects.
3. Formula execution calls `resolve_formula(formula, formula_runtime_function_registry, context)`.
4. `get("provider.path")` reads from a runtime formula context, which delegates
   the first path segment to a registered data provider.

Core files:

- `backend/src/baserow/core/formula/types.py`
- `backend/src/baserow/core/formula/field.py`
- `backend/src/baserow/core/formula/serializers.py`
- `backend/src/baserow/core/formula/__init__.py`
- `backend/src/baserow/core/formula/runtime_formula_context.py`
- `backend/src/baserow/core/formula/registries.py`
- `backend/src/baserow/core/formula/runtime_formula_types.py`
- `web-frontend/modules/core/runtimeFormulaContext.js`
- `web-frontend/modules/core/dataProviderTypes.js`
- `web-frontend/modules/core/formula/**`

## Formula Value Storage

Use the existing field types instead of plain text or JSON fields:

- `FormulaField` stores a single `BaserowFormulaObject`.
- `JSONFormulaField` stores nested objects/lists that contain one or more
  `BaserowFormulaObject` values.
- `BaserowFormulaObject.create("")` or an explicit
  `BaserowFormulaObject(formula="", mode=..., version=...)` is the normal default.

When exposing formula values through the API, use `FormulaSerializerField`.
For nested formula objects, make sure the serializer exposes each formula property
with `FormulaSerializerField`; `collect_json_formula_field_properties()` depends
on that serializer metadata for `JSONFormulaField`.

Important behavior:

- Empty formulas resolve to an empty string.
- Raw mode returns the raw formula string without parsing or executing it.
- Simple and advanced modes are parsed and validated.
- `FormulaSerializerField` requires `context["application_type"]` unless the
  formula is blank or raw, because it needs the application data provider registry
  to validate `get(...)` calls.

## Runtime Formula Execution

Use `resolve_formula()` for backend execution:

```python
from baserow.core.formula import resolve_formula
from baserow.core.formula.registries import formula_runtime_function_registry

result = resolve_formula(
    formula_object,
    formula_runtime_function_registry,
    dispatch_context,
)
```

The context is usually a dispatch context that inherits or behaves like
`RuntimeFormulaContext`. Its `__getitem__` receives dotted paths such as
`data_source.12.field_34`, splits the first segment as the provider type, and
calls that provider's `get_data_chunk(dispatch_context, rest)`.

Frontend execution uses `RuntimeFormulaContext` in
`web-frontend/modules/core/runtimeFormulaContext.js`. It has the same provider
delegation model: `context.get("provider.path")` calls the registered frontend
data provider's `getDataChunk(applicationContext, rest)`.

## Runtime Functions

Runtime functions are registered in `formula_runtime_function_registry`.

To add or update one:

1. Add a `RuntimeFormulaFunction` subclass, usually in
   `backend/src/baserow/core/formula/runtime_formula_types.py`.
2. Set a unique lowercase `type`.
3. Define `args` with `BaserowRuntimeFormulaArgumentType` instances, or override
   `validate_number_of_args()` / `validate_type_of_args()` for variadic behavior.
4. Implement `execute(context, args)`.
5. Register it where the existing runtime functions are registered.
6. Add or update frontend parser/execution/autocomplete support if the function
   must work client-side or appear in the formula editor.
7. Add backend tests for validation and execution.

The built-in `get` function validates that the first path segment exists in the
active application data provider registry. If adding a provider, make sure the
provider is registered before expecting `get("new_provider...")` to validate.

## Backend Data Providers

Backend data providers subclass `DataProviderType` from
`backend/src/baserow/core/formula/registries.py`.

Minimum implementation:

```python
from typing import List

from baserow.core.formula.registries import DataProviderType


class ExampleDataProviderType(DataProviderType):
    type = "example"

    def get_data_chunk(self, dispatch_context, path: List[str]):
        key, *rest = path
        return ...
```

Implement only the hooks the provider needs:

- `get_data_chunk(dispatch_context, path)`: resolves `get("provider.path")`.
- `import_path(path, id_mapping, **kwargs)`: rewrites IDs during import,
  duplication, or template install.
- `is_valid(path)`: validates `get(...)` paths during formula validation.
- `extract_properties(path, **kwargs)`: reports service/table fields used by
  formulas, typically for data source dependency or property extraction.
- `post_dispatch(dispatch_context, workflow_action, dispatch_result)`: runs
  provider-specific logic after workflow action dispatch.

Builder-specific providers usually subclass `BuilderDataProviderType` in:

- `backend/src/baserow/contrib/builder/data_providers/data_provider_types.py`
- `backend/src/baserow/contrib/builder/data_providers/registries.py`

Automation-specific providers usually subclass `AutomationDataProviderType` in:

- `backend/src/baserow/contrib/automation/data_providers/data_provider_types.py`
- `backend/src/baserow/contrib/automation/data_providers/registries.py`

Registration points:

- Builder: `backend/src/baserow/contrib/builder/apps.py`
- Automation: `backend/src/baserow/contrib/automation/apps.py`
- New application types need their own `DataProviderTypeRegistry`, exposed from
  the application type as `data_provider_type_registry`.

Follow existing provider patterns:

- Data source and previous node providers load a service/node, dispatch or read
  stored results, call `service.get_type().prepare_value_path(...)`, then read
  with `get_value_at_path(...)`.
- List-returning services consume the next path segment as the row/item selector
  before preparing the remaining value path.
- Providers that reference IDs must implement `import_path()` so copied builders,
  automations, templates, and imports point at the new IDs.
- Providers should raise `InvalidRuntimeFormula` or `InvalidFormulaContext` when
  the context is malformed or references deleted objects, matching nearby code.

## Dispatch Context Data

Some providers resolve entirely from backend state. Others need frontend runtime
data, such as form input or page parameters.

For builder providers, implement `get_request_serializer()` on the backend if the
dispatch API must accept provider data. On the frontend, implement one or both:

- `getDataSourceDispatchContext(applicationContext)`
- `getActionDispatchContext(applicationContext)`

`DataProviderType.getAllDataSourceDispatchContext(...)` and
`DataProviderType.getAllActionDispatchContext(...)` collect these objects and send
them to backend dispatch endpoints.

Keep the provider key stable. The backend receives the object under the provider
`type`, so `type = "form_data"` pairs with the frontend provider whose
`static getType()` returns `"form_data"`.

## Frontend Data Providers

Frontend data providers subclass `DataProviderType` from
`web-frontend/modules/core/dataProviderTypes.js`.

Minimum implementation:

```js
import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'

export class ExampleDataProviderType extends DataProviderType {
  static getType() {
    return 'example'
  }

  get name() {
    return this.app.$i18n.t('dataProviderType.example')
  }

  getDataChunk(applicationContext, path) {
    return ...
  }

  getDataSchema(applicationContext) {
    return { type: 'object', properties: {} }
  }
}
```

Implement these methods when relevant:

- `initOnce(applicationContext)`: load application-wide provider data.
- `init(applicationContext)`: load page/node-level provider data.
- `needBackendContext`: return `true` if initialization depends on backend context.
- `getDataChunk(applicationContext, path)`: resolves formulas client-side.
- `getDataContent(applicationContext)`: returns current data for explorer previews.
- `getDataSchema(applicationContext)`: returns JSON-schema-like data nodes for
  `get("provider.path")`.
- `getContextDataSchema(applicationContext)`: returns schema for request/context
  data supplied by the user or runtime.
- `getPathTitle(applicationContext, pathParts)`: converts IDs/path tokens to
  user-facing names in the formula input.
- `isValid(pathParts)`: rejects invalid paths in frontend validation when needed.

Registration points:

- Builder: `web-frontend/modules/builder/plugin.js` under `builderDataProvider`.
- Automation: `web-frontend/modules/automation/plugin.js` under
  `automationDataProvider`.
- New surfaces should register a namespace and pass that registry collection into
  the formula input/runtime context.

Use schema objects with `title`, `type`, `properties`, `items`, and optional
`order` fields. The base `getNodes()` implementation turns these schemas into
the formula data explorer tree.

## Import, Export, And Duplication

Any formula path that contains an object ID must be migrated during import or
duplication.

Backend helpers and examples:

- Builder formula import: `backend/src/baserow/contrib/builder/formula_importer.py`
- Automation formula import:
  `backend/src/baserow/contrib/automation/formula_importer.py`
- Builder property extraction:
  `backend/src/baserow/contrib/builder/formula_property_extractor.py`
- Provider `import_path()` implementations in builder and automation data providers.
- Type-specific `formula_generator(...)` methods on element/workflow/service types
  for nested formula fields.

When adding formula properties to a model/type:

1. Store them with `FormulaField` or `JSONFormulaField`.
2. Expose them with `FormulaSerializerField`.
3. Add them to the type's formula generator/import flow if the type has custom
   nested formula structures.
4. Implement provider `import_path()` for every provider path segment that stores
   copied object IDs.
5. Add import/export or duplication tests when formulas can reference copied
   objects.

## Common Implementation Checklist

For a new runtime formula-backed feature:

1. Identify the product surface: builder, automation, dashboard, or another app.
2. Choose the formula storage field: `FormulaField` for one value,
   `JSONFormulaField` for nested repeated formula values.
3. Add `FormulaSerializerField` API fields and pass serializer context with
   `application_type`.
4. Confirm formulas are resolved with the right dispatch context and
   `formula_runtime_function_registry`.
5. If formulas need new data, add matching backend and frontend data providers.
6. Register providers in the backend app config and frontend plugin.
7. Add frontend schema/content/path-title methods so the data explorer and editor
   show the provider correctly.
8. Add dispatch context serialization when backend resolution needs frontend data.
9. Add import path rewriting for IDs embedded in `get(...)` paths.
10. Add targeted backend and frontend tests.

## Testing

Run the narrowest relevant tests first.

Backend areas to inspect:

- `backend/tests/baserow/core/formula/**`
- `backend/tests/baserow/contrib/builder/**`
- `backend/tests/baserow/contrib/automation/**`
- API serializer tests near the feature being changed.
- Import/export/duplication tests when paths contain IDs.

Frontend areas to inspect:

- `web-frontend/test/unit/core/**`
- `web-frontend/test/unit/builder/**`
- `web-frontend/test/unit/automation/**`
- Component tests around formula input/data explorer when schema or path titles
  change.

Useful commands:

- `just b test backend/tests/path/to/test.py`
- `just f yarn test:core web-frontend/test/unit/path/to/test.spec.js`
- `just f test`

Minimum validation before finishing:

1. Backend formula validation accepts valid `get("provider.path")` values and
   rejects invalid provider names/paths.
2. Backend formula execution resolves the expected values.
3. Frontend formula execution resolves the same paths where client-side execution
   is supported.
4. The formula data explorer shows useful names, schemas, and icons.
5. Import/duplication rewrites ID paths correctly.
6. Provider registrations exist on both backend and frontend when applicable.

## Search Patterns

Use these searches before editing:

Use `rg -n "<pattern>" <paths>` as a faster equivalent when `rg` is available.

```bash
grep -RInE "class .*DataProviderType|DataProviderTypeRegistry|data_provider_type_registry" backend/src web-frontend/modules
grep -RInE "FormulaField|JSONFormulaField|FormulaSerializerField|BaserowFormulaObject" backend/src/baserow/contrib backend/src/baserow/core/formula
grep -RInE "resolve_formula\\(|formula_runtime_function_registry|RuntimeFormulaFunction" backend/src
grep -RInE "getDataChunk|getDataSchema|getDataContent|getContextDataSchema|getPathTitle" web-frontend/modules
grep -RInE "formula_generator|import_formula|import_path|extract_properties" backend/src/baserow/contrib
```
