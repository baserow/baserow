---
name: Add Or Update Builder Element Type
description: Add or update a Baserow Application Builder element type across backend models, backend ElementType registration, frontend element registry/components/forms/icons/translations, migrations, and targeted tests. Use when creating or changing an element shown in the builder add-element modal, page preview, public page rendering, form elements, collection elements, container elements, or enterprise-only builder elements.
version: 1.0.0
---

# Add Or Update Builder Element Type

Use this skill when a task involves a new or changed Application Builder element
type. Builder elements usually have both backend and frontend representations, and
many also need migrations, public rendering behavior, import/export behavior, and
tests.

Prefer copying the nearest existing element with the same behavior:

- Basic display element: `HeadingElement`, `TextElement`, `ImageElement`
- Navigation/action element: `LinkElement`, `ButtonElement`, `MenuElement`
- Form input: `InputTextElement`, `CheckboxElement`, `ChoiceElement`
- Collection-backed element: `TableElement`, `RepeatElement`, `RecordSelectorElement`
- Container element: `ColumnElement`, `SimpleContainerElement`, `FormContainerElement`
- Multi-page container: `HeaderElement`, `FooterElement`
- Enterprise-only element: `AuthFormElement`, `FileInputElement`

## First Step

Before editing, identify:

1. Open source core OSC, or Enterprise licensing (no premium for app builder elements).
   Prompt the user for that information.
2. Basic, form, collection, container, or multi-page behavior.
3. Whether the type adds persisted fields.
4. Whether fields are formulas and need formula import/export support.
5. Whether the element has workflow events, form data, child elements, or data source
   content.

Then inspect the closest existing implementation with `grep` instead of starting
from the base class. If `rg` is available, it is a faster equivalent for the same
patterns and target paths.

Useful searches:

- `grep -RInE "class .*Element\\(" backend/src/baserow/contrib/builder/elements/models.py enterprise/backend/src/baserow_enterprise/builder/elements/models.py`
- `grep -RInE "class .*ElementType\\(" backend/src/baserow/contrib/builder/elements/element_types.py enterprise/backend/src/baserow_enterprise/builder/elements/element_types.py`
- `grep -RInE "element_type_registry.register" backend/src/baserow/contrib/builder/apps.py enterprise/backend/src/baserow_enterprise/apps.py`
- `grep -RInE "class .*ElementType extends" web-frontend/modules/builder/elementTypes.js enterprise/web-frontend/modules/baserow_enterprise/builder/elementTypes.js`
- `grep -RInE "\\$registry.register\\('element'" web-frontend/modules/builder/plugin.js enterprise/web-frontend/modules/baserow_enterprise/plugin.js`
- `grep -RInE "\"elementType\\." web-frontend/modules/builder/locales/en.json enterprise/web-frontend/modules/baserow_enterprise/locales/en.json`

## Backend Checklist

For an OSC element, start in:

- `backend/src/baserow/contrib/builder/elements/models.py`
- `backend/src/baserow/contrib/builder/elements/element_types.py`
- `backend/src/baserow/contrib/builder/apps.py`
- `backend/src/baserow/contrib/builder/migrations/`

For an enterprise element, use:

- `enterprise/backend/src/baserow_enterprise/builder/elements/models.py`
- `enterprise/backend/src/baserow_enterprise/builder/elements/element_types.py`
- `enterprise/backend/src/baserow_enterprise/apps.py`
- `enterprise/backend/src/baserow_enterprise/migrations/`

When adding or updating a backend element:

1. Add or update the Django model if new fields are persisted.
2. Pick the right base model or mixin: `Element`, `FormElement`, `CollectionElement`,
   `ContainerElement`, `MultiPageElement`, or the enterprise equivalent.
3. Add an `ElementType` subclass with stable `type` and `model_class`.
4. Set `allowed_fields`, `serializer_field_names`, and
   `request_serializer_field_names` when create/update input differs from output.
5. Add `simple_formula_fields` for fields stored as formulas.
6. Define `SerializedDict` annotations for all serialized custom fields.
7. Override `serializer_field_overrides` for formula fields, files, nested objects,
   or custom validation.
8. Implement `get_pytest_params` with enough valid data for generic element tests.
9. Add hooks such as `prepare_value_for_db`, `after_create`, `after_update`,
   `before_delete`, `import_context_addition`, or `import_serialized` only when the
   element has nested records, workflow events, files, or derived state.
10. Register the type in the relevant `apps.py`.
11. Add a migration for model changes.

Formula-backed Django fields should use the repo's formula field types and serializer
patterns from nearby elements. Do not treat formula objects as plain strings unless
the existing equivalent does.

## Frontend Checklist

For an OSC element, start in:

- `web-frontend/modules/builder/elementTypes.js`
- `web-frontend/modules/builder/plugin.js`
- `web-frontend/modules/builder/components/elements/components/`
- `web-frontend/modules/builder/components/elements/components/forms/general/`
- `web-frontend/modules/builder/assets/icons/`
- `web-frontend/modules/builder/locales/en.json`
- `web-frontend/modules/core/assets/scss/components/builder/elements/`

For an enterprise element, use:

- `enterprise/web-frontend/modules/baserow_enterprise/builder/elementTypes.js`
- `enterprise/web-frontend/modules/baserow_enterprise/plugin.js`
- `enterprise/web-frontend/modules/baserow_enterprise/builder/components/elements/`
- `enterprise/web-frontend/modules/baserow_enterprise/assets/images/builder/`
- `enterprise/web-frontend/modules/baserow_enterprise/assets/scss/components/`

When adding or updating frontend behavior:

1. Add or update the Vue render component used in preview/public rendering.
2. Add or update the general form component if the element has editable fields.
3. Use existing mixins when relevant: `formElement`, `formElementForm`,
   `collectionElement`, `collectionElementForm`, `containerElement`,
   `elementForm`, `styleForm`, or `resolveFormula`.
4. Add or update the frontend `ElementType` class with `static getType()`, `name`,
   `description`, `image`, `component`, `generalFormComponent`, defaults, validators,
   `getDisplayName`, and error handling as needed.
5. Register the type in the relevant plugin with `$registry.register('element', ...)`.
6. Add an icon import and matching SVG asset for the add-element modal.
7. Add translations for the element name, description, form labels, validation
   messages, and empty/error states.
8. Add SCSS only when the component needs element-specific styling; otherwise rely on
   shared builder styles.

Match existing Vue 3 semantics. If a file contains JSX, use `.jsx` or `.tsx`.

## Common Behavior Hooks

Check these hooks before inventing new behavior:

- Placement and child restrictions: backend `validate_place`, frontend
  `isDisallowedReason`, `child_types_allowed`, and container mixins.
- Form elements: backend `FormElementTypeMixin` or `InputElementType`; frontend
  `FormElementType`, `formElement`, `formElementForm`, `formDataType`, `isValid`,
  `getError`, and `isInError`.
- Collection elements: backend `CollectionElementTypeMixin` or
  `CollectionElementWithFieldsTypeMixin`; frontend `CollectionElementTypeMixin`,
  `collectionElement`, `collectionElementForm`, `schema_property`, fields, sorting,
  filtering, search, and `data_source_id`.
- Containers: backend `ContainerElementTypeMixin`; frontend
  `ContainerElementTypeMixin` and child rendering/drop zones.
- Workflow events: use existing `ClickEvent`, `SubmitEvent`, dynamic event UID, and
  import/export patterns from button, form container, table, or menu elements.
- Files: use existing user file serializer/import/export patterns from image or
  enterprise file input elements.

## Testing Expectations

Add or update targeted tests for the behavior touched.

Backend starting points:

- `backend/tests/baserow/contrib/builder/elements/test_element_types.py`
- `backend/tests/baserow/contrib/builder/elements/test_element_handler.py`
- `backend/tests/baserow/contrib/builder/elements/test_element_service.py`
- `backend/tests/baserow/contrib/builder/api/elements/`
- `enterprise/backend/tests/baserow_enterprise_tests/builder/elements/test_element_types.py`

Frontend starting points:

- `web-frontend/test/unit/builder/elementTypes.spec.js`
- `web-frontend/test/unit/builder/components/elements/components/`
- `enterprise/web-frontend/test/unit/enterprise/builder/elementTypes.spec.js`

Useful validation commands:

- `just b test tests/baserow/contrib/builder/elements/test_element_types.py`
- `just b test tests/baserow/contrib/builder/api/elements/`
- `just b test enterprise/backend/tests/baserow_enterprise_tests/builder/elements/test_element_types.py`
- `just f yarn test:core --run test/unit/builder/elementTypes.spec.js`
- `just f yarn test:core --run test/unit/builder/components/elements/components/<Element>.spec.js`
- `just f yarn test:enterprise --run ../enterprise/web-frontend/test/unit/enterprise/builder/elementTypes.spec.js`

Minimum checks before finishing:

1. Backend and frontend type strings match exactly.
2. The element is registered in both backend and frontend where applicable.
3. Create/update serializers accept only intended fields.
4. Public serialization includes all required fields.
5. Formula fields resolve, import, export, and duplicate correctly.
6. Migrations exist for model changes.
7. Required translations and icon assets exist.
8. The narrowest relevant backend and frontend tests pass, or failures are reported.

## Guardrails

- Do not rename a persisted `type` string unless the user explicitly wants a breaking
  migration.
- Do not add frontend-only elements when the backend API needs to persist them.
- Do not add backend fields without a migration.
- Do not forget generic `get_pytest_params`; many builder tests rely on it.
- Do not bypass formula serializers for fields declared in `simple_formula_fields`.
- Do not add broad abstractions for one element. Copy the closest local pattern first.
- Do not place enterprise-only types in core registries.
