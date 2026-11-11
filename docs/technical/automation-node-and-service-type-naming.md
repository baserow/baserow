# Automation node and service type naming conventions

Automation node types wrap integration service types, and the same service types
also back builder data sources, builder workflow actions and dashboard data sources.
The names below let a reader go from a node type to its model, to the service type it
wraps, to the form that configures it and to the fixture that creates it in tests
without looking up the `type` string. The convention covers class, function and file
names only: registry `type` strings and Django model names are persisted in API
payloads, exports, templates and migrations, and are never renamed for naming
reasons.

`<Prefix>` is the integration family the service type already uses (`Core`,
`LocalBaserow`, `Slack`, `AIAgent`); `<Thing>` is what the node or service does
(`DeleteRow`, `Periodic`, `RowsDeleted`).

| Layer | Pattern | Examples |
| --- | --- | --- |
| Backend node model (unchanged) | `<Prefix><Thing>ActionNode` / `<Prefix><Thing>TriggerNode`; bases `AutomationActionNode` / `AutomationTriggerNode` | `LocalBaserowDeleteRowActionNode`, `CoreHTTPTriggerNode` |
| Backend node type | the model name plus `Type`: `<Prefix><Thing>ActionNodeType` / `<Prefix><Thing>TriggerNodeType`; bases `AutomationActionNodeType` / `AutomationTriggerNodeType`; registry base `AutomationNodeType`; mixins `<Name>NodeTypeMixin` | `LocalBaserowDeleteRowActionNodeType`, `LocalBaserowRowsDeletedTriggerNodeType`, `ContainerNodeTypeMixin` |
| Backend service type | `<Prefix><Thing>ServiceType` for action and data services; `<Prefix><Thing>TriggerServiceType` for event services (anything using `TriggerServiceTypeMixin`) | `LocalBaserowDeleteRowServiceType`, `CorePeriodicTriggerServiceType`, `LocalBaserowRowsDeletedTriggerServiceType` |
| Backend service model (unchanged) | whatever it is today | `CorePeriodicService`, `LocalBaserowRowsDeleted` |
| `type` strings (unchanged) | a service-backed node type's `type` equals the wrapped service type's `type` | `local_baserow_delete_row`, `periodic` |
| Backend test fixtures | `create_<prefix>_<thing>_action_node` / `create_<prefix>_<thing>_trigger_node` | `create_core_goto_action_node`, `create_core_http_trigger_node` |
| Frontend node type | the backend class name; base `NodeType`; mixins `ActionNodeTypeMixin`, `TriggerNodeTypeMixin`, `ContainerNodeTypeMixin`, `UtilityNodeTypeMixin` | `CoreGotoActionNodeType`, `LocalBaserowRowsDeletedTriggerNodeType` |
| Frontend service type | the backend class name; the surface is expressed by the mixin (`WorkflowActionServiceTypeMixin`, `DataSourceServiceTypeMixin`, `TriggerServiceTypeMixin`), never by a `Workflow` or `DataSource` word in the class name | `LocalBaserowDeleteRowServiceType`, `CorePeriodicTriggerServiceType` |
| Frontend service form | the service type name with `Type` replaced by `Form` | `LocalBaserowDeleteRowServiceForm.vue`, `CorePeriodicTriggerServiceForm.vue` |
| Casing | acronyms stay upper-case | `HTTP`, `SMTP`, `CSV`, `XLS`, `AI` |

Frontend-only intermediate bases follow the same shape: `LocalBaserowNodeType` and
`LocalBaserowSignalTriggerNodeType` sit between `NodeType` and the concrete Local
Baserow node types.

## Known legacy exceptions

These names predate the convention and are kept on purpose: the `User` suffix on the
Local Baserow data-source service types (`LocalBaserowGetRowUserServiceType`,
`LocalBaserowListRowsUserServiceType`, `LocalBaserowAggregateRowsUserServiceType` and
the premium `LocalBaserowGroupedAggregateRowsUserServiceType`),
`DataSourceLocalBaserowTableServiceType` on the frontend, the three data-source form
components `LocalBaserowGetRowForm.vue`, `LocalBaserowListRowsForm.vue` and
`LocalBaserowAggregateRowsForm.vue`, and the builder workflow action type names
(`CoreHttpRequestActionType`, `DeleteRowWorkflowActionType`, ...). They are shared
builder and dashboard code, or builder-only code, so renaming them buys automation
nothing and would touch modules this convention does not own.

## Follow-ups

Each of these is a separate change if someone wants to close the gap:

- Drop the `User` suffix from the backend data-source service types; the frontend
  already uses `LocalBaserowGetRowServiceType`, `LocalBaserowListRowsServiceType` and
  `LocalBaserowAggregateRowsServiceType`.
- Give the builder workflow action types one shape on both sides, with upper-case
  acronyms (`HTTP`, not `Http`).
- Move the `DataSource` word of `DataSourceLocalBaserowTableServiceType` into its
  mixin, as the frontend service type row requires.
- Rename the three data-source form components after their service types
  (`LocalBaserowGetRowServiceForm.vue`, ...), together with
  `localBaserowGetRowForm.spec.js`.
