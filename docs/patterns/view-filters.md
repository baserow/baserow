# View filters

How to add or change a view filter. The unusual constraint here is that
**every filter has two implementations that must behave identically** —
one in Python that builds a Django ORM `Q` object, one in JavaScript
that filters rows in memory for instant feedback. Drift between the
two is the #1 source of bugs in this corner of the codebase.

For the broader view system see
[Database plugin](../technical/database-plugin.md). For the filter
registry pattern see [Registries](registries.md) (backend) and
[Frontend registries](frontend-registries.md).

## Why two implementations

When the user types into a filter, the frontend doesn't want to wait
for an HTTP round-trip before highlighting which rows match. The
in-memory rows in the Vuex store are filtered locally, the matching
ones stay visible, the rest fade out. The same filter is also sent to
the backend, which re-runs it as part of the row query so paginated
and freshly-loaded rows obey the same rule.

The matching rules **must agree**. If the JS says a row matches and
the backend says it doesn't, the user sees a row that vanishes on the
next page load. If the JS says it doesn't and the backend says it
does, the user sees a row appear after a click. Either is a bug.

There's no shared engine: Baserow deliberately keeps a backend SQL
implementation and a frontend in-memory implementation so the UI can respond
without waiting for the server. Write both halves, test both halves, and keep
them in sync on every change.

## Backend half

`backend/src/baserow/contrib/database/views/view_filters.py`. The base
class is in `registries.py`:

```python
class ExampleFilterType(ViewFilterType):
    type = "equal"
    compatible_field_types = ["text", "long_text", "url", "email"]

    def get_filter(self, field_name, value, model_field, field):
        return Q(**{field_name: value})
```

Three things to set:

- **`type`** — unique string. Must match the frontend's
  `static getType()`.
- **`compatible_field_types`** — list of `FieldType.type` strings or
  predicate functions taking `(field)`. Determines which field types
  the user can apply this filter to. The
  `FieldType.get_compatible_filter_field_type(field)` indirection runs
  first, so a field can alias itself to a different type for
  filter-compatibility purposes (a formula returning a number is
  compatible with number filters via this alias).
- **`get_filter(field_name, value, model_field, field)`** — returns a
  `Q` or `AnnotatedQ` (the annotated variant lets you attach
  `.annotate()` expressions that your `Q` then references).

### `AnnotatedQ` — the escape hatch

When the filter needs a derived value that doesn't already exist on
the table, return `AnnotatedQ(annotation={...}, q=Q(...))`. The
annotation is applied to the queryset before the filter; everything
stays in SQL.

Real example — the `length_is_lower_than` text filter
(`LengthIsLowerThanViewFilterType`):

```python
def get_filter(self, field_name, value, model_field, field):
    if value == 0:
        return Q()
    return AnnotatedQ(
        annotation={f"{field_name}_len": Length(field_name)},
        q={f"{field_name}_len__lt": int(value)},
    )
```

Use this rather than reaching for Python-level post-filtering. Python
post-filtering breaks pagination and sort ordering.

### Other hooks

| Hook | When |
|---|---|
| `get_preload_values(view_filter)` | Filters that reference other rows (`link_row_has`) — preload display values for the configuration UI. |
| `get_export_serialized_value` / `set_import_serialized_value` | When the filter value is an id that needs to be remapped during snapshot / template import. |
| `default_filter_on_exception` | What `Q` to return if the filter value can't be parsed (default: match no rows). |

### Validate the filter value

The serializer used by the filter API doesn't know the field's type at
DRF deserialisation time — it accepts any string. Validate inside
`get_filter` and return `self.default_filter_on_exception()` if the
value is malformed. Don't raise — a bad filter value should hide rows,
not break the page.

## Frontend half

`web-frontend/modules/database/viewFilters.js`. Base class at the top
of the file:

```javascript
import { ViewFilterType } from '@baserow/modules/database/viewFilters'

export class EqualViewFilterType extends ViewFilterType {
  static getType() { return 'equal' }

  getName() { return this.app.$i18n.t('viewFilter.is') }

  getInputComponent(field) {
    return ViewFilterTypeText
  }

  getCompatibleFieldTypes() {
    return ['text', 'long_text', 'url', 'email']
  }

  matches(rowValue, filterValue, field, fieldType) {
    if (filterValue === '') return true
    rowValue = rowValue === null ? '' : rowValue
    return rowValue.toString() === filterValue.toString()
  }
}
```

Methods to implement:

- **`static getType()`** — must match backend `type`.
- **`getName()`** / **`getExample()`** — display label and API-doc example.
- **`getCompatibleFieldTypes()`** — must match backend
  `compatible_field_types`.
- **`getInputComponent(field)`** — the Vue component used to capture
  the filter value (text, number, date picker, single-select picker, …).
- **`matches(rowValue, filterValue, field, fieldType)`** — the JS
  twin of `get_filter`. Returns `true`/`false`. **Must produce the
  same answer as the backend for every input the user can construct.**

Register from the database module's `plugin.js`:

```javascript
$registry.register('viewFilter', new EqualViewFilterType(context))
```

### Collation gotchas — where the two halves drift

These are the cases where a careless second implementation diverges:

- **Empty string vs null.** Backend treats both as "no filter". JS
  must do the same — and must coerce row values consistently (the
  `rowValue === null ? '' : rowValue` line above).
- **Case sensitivity.** Postgres `ILIKE` is case-insensitive; raw JS
  `===` is not. Use `.toLowerCase()` on both sides if the backend uses
  `ILIKE`.
- **Whitespace.** Postgres collation may treat trailing whitespace
  differently than `String.trim()`. Match exactly what the backend
  does — usually `.trim()` both values on both sides.
- **Number parsing.** `parseInt("5.7")` → `5`. `int("5.7")` →
  `ValueError`. Decide and align — usually parse leniently on both
  sides.
- **Null / undefined for empty cells.** Backend gets `NULL`; the JS
  may get `null`, `undefined`, `''`, or `0` depending on the field
  type. Normalise before comparison.
- **Multi-select / select option ids vs names.** Filter values are
  ids; row values are nested objects. `matches` must traverse the
  object to pull out the id.

Whenever a filter looks "wrong" on the frontend but right on the
backend (or vice versa), one of these is almost always the cause.

## Adding a new filter — the checklist

1. **Pick the `type` string** — short, lowercase, snake_case
   (`equal`, `length_is_lower_than`, `link_row_has`).
2. **Backend:**
   - Subclass `ViewFilterType` in `view_filters.py`.
   - Set `type` and `compatible_field_types`.
   - Implement `get_filter`. Use `AnnotatedQ` if you need derived
     columns.
   - Register in the database app's `apps.py`
     (`view_filter_type_registry.register(...)`).
   - Test in `backend/tests/baserow/contrib/database/view/`.
3. **Frontend:**
   - Subclass `ViewFilterType` in `viewFilters.js`.
   - Set `getType()` to match.
   - Set `getName()`, `getInputComponent`, `getCompatibleFieldTypes`.
   - Implement `matches` to mirror `get_filter`.
   - Register in `modules/database/plugin.js`.
   - Test in `web-frontend/test/unit/database/...`.
4. **Cross-check.** Write parity tests: for a handful of inputs,
   assert backend and frontend produce the same outcome. The codebase
   has a `arrayViewFiltersMatch.spec.js` style test that exercises
   this — match it.
5. **Premium / enterprise.** If the filter is premium, register it
   from the premium plugin. The base classes are shared.

## Anti-patterns

- **Implementing only one half.** The user sees inconsistent results.
  Always both halves; always tests for both.
- **Post-filtering in Python after the queryset.** Breaks pagination
  and `count()`. Use `AnnotatedQ` instead.
- **Raising from `get_filter` or `matches` on bad input.** Hide rows
  via `default_filter_on_exception` or `return false`.
- **Diverging `compatible_field_types`.** A frontend that lists a
  field type the backend will reject (or vice versa) produces "filter
  silently does nothing" UX.
- **Adding a sixth lookup table mapping field type → behaviour
  inside the filter.** That logic belongs on the `FieldType` (which is
  why `get_compatible_filter_field_type` exists). Push the
  per-type-difference back to the field type's class.

## Related

- [Database plugin](../technical/database-plugin.md) — views and the
  filter machinery.
- [Field system](../patterns/field-system.md) —
  `get_compatible_filter_field_type` lives here.
- [Registries (backend)](registries.md) /
  [Frontend registries](frontend-registries.md) — registration
  mechanics.
- [Architectural patterns](architecture.md) — the broader request flow.
