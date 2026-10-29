# Workspace-level integrations: implementation plan

> Temporary companion to [ADR 013](013-workspace-level-integrations.md). It describes
> how v1 is built so the technical approach can be reviewed in this PR. It is deleted
> once the implementation is reviewed.

Issue: https://github.com/baserow/baserow/issues/6015. The terms *app*, *shared
application*, *workspace integration* and *published copies* are the ADR's.

## Overview

A hidden `SharedApplication` per workspace owns the workspace integrations. The
`Integration` model, `IntegrationSerializer` and the integration URLs do not change.
The work is: a new application type, six workspace-scoped operations, a widened
ownership check, export changes on three paths, trash placement, promotion through the
existing update endpoint, and a workspace settings page plus dropdown grouping.

| ADR decision                                   | Section  |
| ---------------------------------------------- | -------- |
| 1. Hidden shared application                   | 1.1      |
| 2. App or workspace integration                | 1.4      |
| 3. Publish copies, duplicates/snapshots link   | 1.5      |
| 4. Workspace exports and templates flatten     | 1.5      |
| 5. Admins manage, Builders list                | 1.2, 1.3 |
| 6. Every integration type                      | 1.1      |
| 7. Promotion as a one-row move                 | 1.7      |

## 1. Backend

### 1.1 Shared application type

**Model.** `SharedApplication(Application)` in `core/models.py`, no extra fields. One
migration creates the table.

**Type.** `SharedApplicationType` (`type = "shared"`) in a new
`core/application_types.py`, registered in `core/apps.py`:

- `supports_integrations = True` and `supports_integration_type()` returns `True` for
  every type. `supports_user_sources` stays `False`, so the user source endpoints refuse
  it through the existing gate (`core/user_sources/handler.py:210`).
- `supports_snapshots = False`. `create_application`, `export_serialized` and
  `import_serialized` raise `ApplicationOperationNotSupported`, so it cannot be created
  through `POST /api/applications/workspace/<id>/` and never travels in an export.

**Creation.** Lazy, in `CoreHandler.list_applications_in_workspaces()`
(`core/handler.py:1659`): for every listed, non-trashed workspace without a shared app,
lock the workspace row (`select_for_update`) and `get_or_create` it (name `__shared__`,
order `0`). This covers new workspaces, existing ones after the upgrade and workspaces
restored from a backup.

**Visibility.** The shared app stays in `Application.objects`,
`workspace.application_set`, `CoreHandler.get_application()` and the application list
endpoints; the frontend type hides it (2.1). Where it must not travel or be counted, a
new `Application.objects_without_shared` manager (excludes the `SharedApplication`
content type) and `Workspace.application_set_without_shared()` are used, following
`Builder.visible_pages` (`contrib/builder/models.py:149`):

| Site                            | Today                                                             |
| ------------------------------- | ----------------------------------------------------------------- |
| Workspace export                | `core/handler.py:2000`, `workspace.application_set.all()`         |
| Export job of selected apps     | `core/import_export/handler.py:463`, `export_workspace_applications` |
| User templates                  | `core/user_templates/handler.py`                                  |
| Trash structure listing         | `core/trash/handler.py:684`, `application_set_including_trash()`  |
| Admin workspace statistics      | `api/admin/workspaces/views.py:48`, `Count("application")`        |

Aggregates bypass managers, so the `Count` is filtered explicitly.

**Guards.** `CoreHandler.delete_application`, `duplicate_application`,
`update_application`, snapshot creation and template creation refuse a shared app
(`ApplicationOperationNotSupported`, mapped to 400). Reordering needs nothing: the
sidebar sends the visible ids and `order_objects` accepts a partial list.

### 1.2 Permissions

Six operations in `core/integrations/operations.py`. The workspace-scoped ones extend
`WorkspaceCoreOperationType` (precedent `core/agents/operations.py`), the item ones
`IntegrationOperationType`.

| Operation                        | Context     | RBAC role | Basic permission manager |
| -------------------------------- | ----------- | --------- | ------------------------ |
| `workspace.list_integrations`    | workspace   | Builder   | every member             |
| `workspace.create_integration`   | workspace   | Admin     | `ADMIN_ONLY_OPERATIONS`  |
| `workspace.order_integrations`   | workspace   | Admin     | `ADMIN_ONLY_OPERATIONS`  |
| `workspace.integration.update`   | integration | Admin     | `ADMIN_ONLY_OPERATIONS`  |
| `workspace.integration.delete`   | integration | Admin     | `ADMIN_ONLY_OPERATIONS`  |
| `workspace.integration.restore`  | integration | Admin     | `ADMIN_ONLY_OPERATIONS`  |

Registered in `core/apps.py`; roles in `enterprise/.../role/default_roles.py` next to
the agent operations; the Admin ones also in `BasicPermissionManagerType.ADMIN_ONLY_OPERATIONS`
(`core/permission_manager.py:397`). Object scopes and the RBAC queryset filters are
untouched: `application__workspace` resolves through the shared app.

Separate operations are needed because a Builder at workspace level passes the
app-level check on the shared app through the ownership chain (integration → shared
app → workspace) and could otherwise manage every workspace integration.

### 1.3 API and service layer

No new endpoints. The frontend takes the shared app's id from the application list and
tells the levels apart by `application_id`. `IntegrationService`
(`core/integrations/service.py`) picks the operation with
`IntegrationHandler.is_shared_application(application)`
(`application.specific_class is SharedApplication`):

| Call                                       | Shared app                       | Otherwise (today)                 |
| ------------------------------------------ | -------------------------------- | --------------------------------- |
| `GET /api/application/<id>/integrations/`  | `workspace.list_integrations`    | `application.list_integrations`   |
| `POST /api/application/<id>/integrations/` | `workspace.create_integration`   | `application.create_integration`  |
| `PATCH /api/integration/<id>/`             | `workspace.integration.update`   | `application.integration.update`  |
| `DELETE /api/integration/<id>/`            | `workspace.integration.delete`   | `application.integration.delete`  |
| `PATCH /api/integration/<id>/move/`        | `workspace.order_integrations`   | `application.order_integrations`  |
| Restore from trash                         | `workspace.integration.restore`  | `application.integration.restore` |

The views only change for promotion (1.7). The action types in
`core/integrations/actions.py` use `WorkspaceActionScopeType` for workspace
integrations, so undo works from the settings page and from inside an app.

### 1.4 Using a workspace integration from an app

Every consumer check goes through `IntegrationHandler.check_integration_usable()`
(`core/integrations/handler.py:136`): services on save and dispatch, user sources,
automation nodes, database button actions, the Local Baserow service types and
`get_integration_for_import`. The `application_id` rule becomes: accept when the
integration belongs to the application, or to the shared app of the application's
workspace. A published copy has no workspace (`application.workspace_id is None`) and
never matches, so published content cannot resolve a workspace integration.
Cross-workspace references stay invalid. No caller changes.

### 1.5 Export and import

An app's export serialises only `get_integrations(application)` (builder
`application_types.py:214`, automation `:98`, dashboard `:103`, database `:344`), so
the workspace integrations its services use are handled per path:

| Path                                               | Config                                | Workspace integrations in the export             | On import                                                              |
| -------------------------------------------------- | ------------------------------------- | ------------------------------------------------ | ---------------------------------------------------------------------- |
| Publish: builder domain, workflow and test clone   | `is_publishing`                       | Inlined as app-level copies with credentials     | Created on the published copy; services remapped to the copy           |
| Duplicate app, snapshot create and restore         | `is_duplicate` and not `is_template`  | Not exported                                     | Services keep the unmapped id when it belongs to the destination workspace's shared app |
| Workspace export, templates                        | `exclude_sensitive_data`, `is_template` or `is_user_template` | Inlined as app-level copies, secrets stripped, origin flag set | Created on the imported app; the flag is ignored                       |

- `IntegrationHandler.export_referenced_workspace_integrations(...)` collects the
  `integration_id` values in the serialised content, loads those owned by the
  workspace's shared app and appends their `export_integration()` output to the app's
  `integrations`, each with an origin flag (name open, see 4). The four application
  types call it after serialising their own integrations and skip it on
  `is_duplicate and not is_template` (the builder already branches on these flags at
  `application_types.py:411`).
- `get_integration_for_import()` (`handler.py:92`) callers pass
  `keep_unmapped = is_duplicate and not is_template`; the widened check in 1.4 then
  accepts the destination workspace's shared app. File imports and templates drop an
  unmapped id as today.
- `IntegrationType.import_serialized` pops the origin flag.
- Local Baserow needs nothing: `export_serialized` keeps the subject on publish and
  `after_import` keeps it on a published copy, re-authorising to the importer otherwise
  (`local_baserow/integration_types.py:170-240`).

### 1.6 Trash

For a workspace integration the service trashes with
`TrashHandler.trash(user, workspace, None, integration)` (agent precedent,
`core/agents/handler.py`), and `IntegrationTrashableItemType`
(`core/integrations/trash_types.py`) returns the workspace from `get_parent`, so the
trash UI lists it under the workspace and never shows `__shared__`.

Restore needs a per-item operation: `TrashHandler.restore_item`
(`core/trash/handler.py:168`) calls `get_restore_operation_type()` without the item. Add
`get_restore_operation_type_for_item(trashed_item)` to `TrashableItemType`, defaulting
to the existing hook, and call it there; the integration type returns
`workspace.integration.restore` for workspace integrations. Other trash types are
unaffected.

The shared app itself cannot be trashed (1.1 guards).

### 1.7 Promotion

`PATCH /api/integration/<id>/` accepts an optional `application_id`
(`UpdateIntegrationSerializer`).

- **View.** The target must be the shared app of the integration's workspace,
  otherwise 400. Demotion later relaxes this.
- **Service.** When `application_id` changes, `update_integration` also checks
  `workspace.create_integration` if the target is the shared app, and
  `workspace.integration.update` if the source is (the undo direction), on top of the
  update permission on the integration.
- **Handler.** `update_integration` records `application_id` in `original_values` and
  `new_values`, like the data source handler does for a page move
  (`contrib/builder/data_sources/handler.py:454`), and places the integration last in
  the target's list.
- **Integration type hook.** A no-op `before_application_change(integration, target,
  user)`. Local Baserow re-authorises a person subject other than the user to the user,
  mirroring the self-only rule in `prepare_values`
  (`local_baserow/integration_types.py:119`); agent subjects are kept.
- **Action.** `UpdateIntegrationActionType` already replays original and new values.
  For an application change it uses `WorkspaceActionScopeType` and records the ids in
  `integration.services` and `integration.user_sources`. `undo` raises when any current
  referencing id is not in that set; the API reports a skipped undo and the traceback
  is stored on the action (`core/action/handler.py:130`).
- **Realtime.** The existing `integration_updated` event carries the new
  `application_id`; the frontend relocates the integration (2.4).

## 2. Frontend

### 2.1 Shared application type

`SharedApplicationType` in `core/applicationTypes.js`: `type = 'shared'`,
`isVisible()` and `canBeCreated()` return `false`, no routes, sidebar or dashboard
component. Registered in `core/plugin.js`. `SidebarWithWorkspace.vue:164,172` already
honour both. The applications store gets a `getSharedApplication(workspace)` getter.

### 2.2 Workspace settings page

`IntegrationsWorkspaceSettingsPageType` in `core/workspaceSettingsPageTypes.js`
(`hasPermission` checks `workspace.list_integrations`), registered beside
`AgentsWorkspaceSettingsPageType` (`core/plugin.js:295`), route `settings-integrations`
in `core/routes.js`, page `core/pages/settings/integrations.vue` and table
`core/components/settings/integrations/WorkspaceIntegrationsTable.vue` modelled on
`AgentsTable.vue`.

The page dispatches `integration/fetch` for the shared app and reads
`integration/getIntegrations(sharedApp)`: no new store or service. Create, edit and
delete reuse `IntegrationCreateEditModal.vue` with the shared app as `application`,
gated by `workspace.create_integration`, `workspace.integration.update` and
`workspace.integration.delete`. Local Baserow rows read "Runs as X in all applications
in this workspace". The delete confirmation has no usage count (follow-up).

### 2.3 Integration dropdown

`IntegrationDropdown.vue` renders two groups: "This application" (the `integrations`
prop) and "Workspace" (the shared app's integrations filtered by `integrationType`).
Props and the eight callers are unchanged. The shared app's integrations are fetched
once when an application is selected (builder, automation and dashboard `select`
hooks). The dashboard store's private `integrations` list reads the merged set.

### 2.4 Realtime

No backend change. The events carry the shared app's `application_id` and
`getApplicationContext` (`builder/realtime.js:25`) finds it in the applications store.
`integration_updated` gains the relocation step the data source handler has for a page
move (`realtime.js:301-313`): when another application holds the integration, move it
before `forceUpdate`. The permitted-user set of the broadcasts is computed with the
existing app-level operations on the shared app, which resolve through the workspace,
so workspace-level Builders receive them.

### 2.5 Promotion action

"Make available to the whole workspace" in `builder/components/settings/IntegrationSettings.vue`
and `automation/components/settings/IntegrationSettings.vue`, shown when the user has
`workspace.create_integration`. The confirmation states that the app keeps working,
published copies change on their next publish, and a Local Baserow integration will run
as the current user. It calls `integration/update` with the shared app's
`application_id` and relocates the row, idempotent with the realtime event.

## 3. Delivery

One migration (`SharedApplication`).

The change is additive. The shared app appears in a workspace's listing
only once the new backend serves it, and the frontend type ships in the same release.
A tab still running the previous bundle throws on an unknown application type
(`populateApplication`, `core/store/application.js:12`) at its next listing until it is
reloaded; this matches any release that adds an application type.

## 4. Open questions for reviewers

1. **Lazy creation in the listing.** A `GET` writes a row under a lock. The
   alternative is creating on first need (first workspace integration or promotion)
   and letting the settings page handle "no shared app yet".
2. **Hiding by content type** in `objects_without_shared`, versus a `shared` boolean
   on `Application` like `Page.shared`. The content type lookup costs one query when
   Django's content type cache is cold.
3. **Keep-link discriminator.** `is_duplicate and not is_template` would be repeated in a few
   places; should it become a named property on `ImportExportConfig`?
4. **Export inlining** by scanning the serialised content for `integration_id`, versus
   a per-application-type query over `integration.services` and
   `integration.user_sources`.
5. **Origin flag** name on exported copies, for example `workspace_level: true`, and
   whether publish exports carry it as well.
6. **Local Baserow promotion**: re-authorise to the promoting Admin with a confirmation,
   or reject and ask the Admin to re-authorise first.
7. **Promotion through `PATCH ... application_id`** versus a dedicated `promote/`
   endpoint.
