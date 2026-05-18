# Frontend architecture

Baserow's frontend is **Vue 3 + Nuxt 3 + Vuex + Vite**. The Baserow-specific
shape is the module/registry layout: frontend modules mirror backend
`contrib/` packages, and each module registers its extension types at startup.

For tool versions and config files see [Tools](../development/tools.md). For
Vue, JSX, SCSS, locale, and test conventions see
[Project conventions](../development/conventions.md).

## Request Flow

```
User interaction
  -> component
  -> Vuex store action
  -> service
  -> backend REST API

Backend websocket event
  -> RealTimeHandler
  -> registered realtime callback
  -> Vuex store force action
  -> component re-render
```

Components dispatch store actions. Store actions call services. Services are
thin axios wrappers and own no state. Realtime handlers dispatch `force<Verb>`
actions because the backend has already done the work.

## Top-Level Layout

`web-frontend/modules/` holds the domain modules:

- `core`: shared app shell, registry, auth, jobs, notifications, services.
- `database`, `builder`, `automation`, `dashboard`, `integrations`: product
  modules that mirror backend contrib packages.
- `premium/web-frontend/modules/baserow_premium/` and
  `enterprise/web-frontend/modules/baserow_enterprise/`: paid-edition modules
  that register into the same extension points.

Other important directories:

- `web-frontend/test/`: Vitest tests and fixtures.
- `web-frontend/stories/`: Storybook stories.
- `web-frontend/locales/`: shared i18n files.
- `web-frontend/config/`: Nuxt runtime configs.
- `web-frontend/public/`: static assets.

## Module Shape

Most modules use the same files:

| File / directory | Role |
|---|---|
| `module.js` | Nuxt module entry: routes, plugins, middleware, locales. |
| `plugin.js` | Vue plugin entry; registers types into `$registry`. |
| `plugin/store.js` | Vuex store registration. |
| `plugin/realtime.js` | Realtime event registration. |
| `realtime.js` | Event handlers that update the store. |
| `components/`, `pages/`, `layouts/` | UI. |
| `store/` | Vuex modules. |
| `services/` | Axios wrappers. |
| `<thing>Types.js` | Registry type classes, such as `fieldTypes.js` or `jobTypes.js`. |

## Registries

`modules/core/registry.js` defines `Registerable`, `Registry`, and the global
`$registry`. Modules register type instances from `plugin.js`:

```javascript
$registry.register('field', new TextFieldType(context))
$registry.register('view', new GridViewType(context))
$registry.register('job', new DuplicateTableJobType(context))
```

Callers should ask the registry for behaviour instead of branching on type
strings. For example, use `this.$registry.get('field', field.type)` and call
methods on the returned `FieldType`.

See [Frontend registries](frontend-registries.md) for the full recipe.

## Store Conventions

Store modules keep state changes in one place:

- **State**: plain objects and arrays.
- **Mutations**: uppercase names such as `ADD_ITEM`, `UPDATE_ITEM`,
  `DELETE_ITEM`, `SET_LOADING`.
- **User actions**: `<verb>` actions call a service and commit on success.
- **Mirroring actions**: `force<Verb>` actions commit without HTTP. Realtime,
  undo, restore, and optimistic updates use these.

That split is important. A local write and a websocket event should eventually
land in the same mutation, otherwise clients drift.

## Services

Services are axios factories:

```javascript
export default (client) => ({
  fetchAll(databaseId) {
    return client.get(`/database/tables/database/${databaseId}/`)
  },
  update(tableId, values) {
    return client.patch(`/database/tables/${tableId}/`, values)
  },
})
```

They return HTTP promises. They do not read or mutate Vuex state.

## Realtime

The backend sends websocket messages with a `type`. Modules register handlers
for those types:

```javascript
realtime.registerEvent('table_created', ({ store }, data) => {
  const database = store.getters['application/get'](data.table.database_id)
  store.dispatch('table/forceUpsert', { database, data: data.table })
})
```

`modules/core/plugins/realTimeHandler.js` owns the socket connection,
subscriptions, reconnects, and dispatch table. Subscriptions match backend
`PageType` registrations; see [WebSockets](../technical/websockets.md).

## Auth and SSR

Normal app requests use JWT auth. The auth store owns the access token, refresh
token, decoded payload, user, permissions, and websocket id. Axios interceptors
attach the token and refresh it when needed.

Nuxt SSR is enabled. Browser-only APIs (`window`, `localStorage`, websockets)
must run behind `process.client`; module-load side effects should be avoided.

## i18n

Source strings live in `en.json` files only. Weblate owns every other locale.
Modules register their locale files from `module.js`. Registry types can call
`this.$t(...)` through `Registerable`.

See [Internationalisation and translations](i18n-translations.md).

## Premium and Enterprise

Paid-edition frontend modules mirror the core module shape and register their
types from their own `plugin.js`. They can import from core modules; core must
not import from premium or enterprise. See
[Editions and licensing](../technical/editions-and-licensing.md#boundary-rules).

## Testing

Frontend tests use Vitest, Vue Test Utils, and the `TestApp` helper under
`web-frontend/test/helpers/`. Run tests through the `just` recipes, not raw
`vitest`. The [write-frontend-unit-test skill](https://github.com/baserow/baserow/blob/develop/.agents/skills/write-frontend-unit-test/SKILL.md)
has the detailed workflow.

## Reading Order

1. `modules/core/registry.js`.
2. A simple type, such as `TextFieldType` in `modules/database/fieldTypes.js`.
3. A store module, such as `modules/database/store/table.js`.
4. A service, such as `modules/database/services/table.js`.
5. `modules/database/realtime.js`.
6. One route page that ties the pieces together.

## Related

- [Architectural patterns](architecture.md) — backend layers.
- [Frontend registries](frontend-registries.md).
- [Realtime end-to-end](realtime-end-to-end.md).
- [Optimistic updates](optimistic-updates.md).
- [Project conventions](../development/conventions.md).
