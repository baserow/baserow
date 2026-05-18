# Frontend registries

The frontend uses the same registry pattern as the backend: every
extension point is a registry of typed instances keyed by a unique
`type` string. If you understand
[backend registries](registries.md), this is the same model — the
frontend just has its own copy of the machinery.

This page is the catalogue and the "how to register a new type" recipe.
For the broader frontend architecture (modules, stores, services,
realtime), read [Frontend architecture](frontend-architecture.md) first.

## The machinery

`web-frontend/modules/core/registry.js`:

- **`Registerable`** — abstract base. Every registered type extends it.
  Owns `getType()` (returns the unique string identifier), `getOrder()`,
  and `$t(key)` for i18n.
- **`Registry`** — the container. API: `registerNamespace`, `register`,
  `unregister`, `get`, `getAll`, `getList`, `getOrderedList`, `exists`.
- **`$registry`** — singleton instance exposed on every Vue component
  (and through Nuxt's `useNuxtApp()`). Set up in
  `modules/core/plugins/registry.js`.

A registration block looks like this (real code,
`modules/database/plugin.js`):

```javascript
export default defineNuxtPlugin({
  name: 'database',
  dependsOn: ['core'],
  setup(nuxtApp) {
    const { $registry } = nuxtApp
    const context = { app: nuxtApp }

    // 1. Declare the namespaces this module owns.
    $registry.registerNamespace('viewFilter')
    $registry.registerNamespace('fieldConstraint')
    $registry.registerNamespace('importer')
    // …

    // 2. Register instances into existing or just-declared namespaces.
    $registry.register('field', new TextFieldType(context))
    $registry.register('field', new LongTextFieldType(context))
    $registry.register('field', new LinkRowFieldType(context))
    $registry.register('view', new GridViewType(context))
    $registry.register('viewFilter', new EqualViewFilterType(context))
    // … hundreds more
  },
})
```

Two things to notice:

- **Namespaces are declared by whichever module owns the abstraction.**
  Core declares `application`, `field`, `view`, `notification`, etc.
  The database module declares the database-specific ones
  (`viewFilter`, `fieldConstraint`, `webhookEvent`, …) because it owns
  those concepts. Premium and enterprise rarely declare new namespaces
  — they register into existing ones.
- **`context = { app: nuxtApp }`** is the standard constructor
  argument. Most type classes need it to access `$i18n`, the store, or
  registries — the constructor stashes it as `this.app`.

## Lookup

In a component:

```javascript
const fieldType = this.$registry.get('field', 'text')      // single instance
const allFields = this.$registry.getAll('field')           // { text: …, number: … }
const fieldList = this.$registry.getList('field')          // [TextFieldType, NumberFieldType, …]
const ordered = this.$registry.getOrderedList('field')     // sorted by getOrder()
const exists = this.$registry.exists('field', 'text')      // boolean
```

If you're writing template branches like
`v-if="field.type === 'text'"` *anywhere outside the registry's own
classes*, you're holding the registry wrong — push the per-type
behaviour onto the `FieldType` subclass and call a method on it.
Otherwise adding a new field type means hunting through every component
that special-cased a string.

## Common namespaces

The most-used namespaces are:

| Namespace | Base class | Purpose |
|---|---|---|
| `application` | `ApplicationType` | Database, builder, automation, dashboard. |
| `field` | `FieldType` | User-table column types. |
| `view` | `ViewType` | Table presentations such as grid, gallery, form, kanban. |
| `viewFilter` | `ViewFilterType` | Per-view filter logic. |
| `notification` | `NotificationType` | Notification renderer and click target. |
| `job` | `JobType` | Long-running task UI, mirroring backend `JobType`. |
| `importer` / `exporter` | Import/export base types | Bulk import sources and export formats. |
| `service` / `integration` | Service/integration base types | Builder and automation integrations. |
| `workflowAction` | `WorkflowActionType` | Builder/automation workflow actions. |

Several auth, permissions, search, database, and UI namespaces exist too. The
complete current list lives in source. Run:

```bash
rg "registerNamespace" \
  web-frontend/modules \
  premium/web-frontend/modules \
  enterprise/web-frontend/modules
```

Treat the tables above as a snapshot.

## How to add a new type

Same shape regardless of namespace. As a worked example, adding a new
field type:

1. **Subclass the base** in the right module's `<thing>Types.js`. For a
   core field type, that's `modules/database/fieldTypes.js`; for a
   premium one, `premium/web-frontend/modules/baserow_premium/fieldTypes.js`.

    ```javascript
    import { FieldType } from '@baserow/modules/database/fieldTypes'

    export class MoodFieldType extends FieldType {
      static getType() { return 'mood' }
      getIconClass() { return 'iconoir-emoji' }
      getName() { return this.app.$i18n.t('fieldType.mood') }

      // Component used in grid view cells:
      getGridViewFieldComponent() { return MoodGridViewField }

      // Component used when editing the row detail:
      getRowEditFieldComponent() { return MoodRowEditField }

      prepareValueForDb(field, value) { /* … */ }
      // …
    }
    ```

2. **Implement the required methods.** The base class
   (`FieldType` here) documents what's mandatory and what's optional.
   The fastest way is to find an existing type whose behaviour is
   closest to yours and copy/diff. For fields the cleanest reference is
   `TextFieldType` (minimal) → `NumberFieldType` (with `allowed_fields`)
   → `LinkRowFieldType` (with cross-table behaviour and signals).

3. **Add the Vue components** referenced by `getGridViewFieldComponent`,
   `getRowEditFieldComponent`, etc. They live under the module's
   `components/<area>/`.

4. **Register the instance from the module's `plugin.js`:**

    ```javascript
    $registry.register('field', new MoodFieldType(context))
    ```

5. **Mirror on the backend** if the field stores data — every frontend
   field type has a matching backend `FieldType` registered into the
   backend's `field_type_registry`. The strings must match
   (`getType() === FieldType.type`). See
   [Field system](field-system.md) for the backend half.

6. **Tests.** Use the `write-frontend-unit-test`
   [skill](https://github.com/baserow/baserow/blob/develop/.agents/skills/write-frontend-unit-test/SKILL.md).
   The fastest entry is copying the spec of the closest existing field
   type and adjusting.

Other namespaces follow the same pattern: subclass → implement → add
any components → register from `plugin.js` → mirror on the backend if
relevant → test.

## When to declare a new namespace

Rarely. Only when you're introducing a *new extension surface* — a new
concept that other code (including premium and enterprise) will want to
plug into. If you only need one or two implementations and they're all
in the same module, a regular class hierarchy is fine.

Signs you actually need a new namespace:

- Multiple modules / editions will register implementations.
- The UI needs to iterate over all implementations (e.g. a picker that
  shows every available kind).
- You're crossing the boundary between core and contrib/premium/enterprise.

If you do add one, declare it from the module that owns the
abstraction, document the base class clearly, and register the initial
implementations from the same `plugin.js`. Premium/enterprise can then
register their own implementations into your namespace without touching
core.

## Premium and enterprise

Same registries, different `plugin.js`. Premium types typically extend
core types and override specific methods:

```javascript
// premium/web-frontend/modules/baserow_premium/fieldTypes.js
import { FieldType } from '@baserow/modules/database/fieldTypes'

export class AIFieldType extends FieldType {
  static getType() { return 'ai' }
  getIconClass() { return 'iconoir-magic-wand' }
  getName() { return this.app.$i18n.t('premiumFieldType.ai') }
  // … overrides for grid/edit components, license gating, etc.
}
```

```javascript
// premium/web-frontend/modules/baserow_premium/plugin.js
$registry.register('field', new AIFieldType(context))
```

The import-boundary rule from
[Editions and licensing](../technical/editions-and-licensing.md#boundary-rules)
applies: premium can import from core, never the other way round.

## Related

- [Frontend architecture](frontend-architecture.md) — the broader
  module / store / service / realtime picture.
- [Registries (backend)](registries.md) — the same pattern server-side.
- [Project conventions](../development/conventions.md) — Vue 3, JSX
  extensions, BEM SCSS, locale rule.
- [Database plugin](../technical/database-plugin.md) and
  [Field system](field-system.md) — current backend context for the
  most common frontend registry counterparts.
