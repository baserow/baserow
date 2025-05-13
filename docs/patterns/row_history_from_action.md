# Row History subsystem

When an action is performed, it can leave row history entries for rows affected. 

A row history entry stores information on:
* which row has been affected
* what action has been performed
* when it was performed
* who did it
* what has been changed.

**Note:** An action can affect multiple rows and, indirectly, related tables/rows. Row history items returned by the action should reflect that.

Row history subsystem is loosely coupled with actions. While the core of row history subystem resides in `database` application, it can handle actions from other Baserow applications with dedicated row history providers class hierarchy.

Also, other applications can add their own row history providers to `baserow.contrib.database.rows.registries.row_history_provider_registry`, which keeps a registry of `baserow.contrib.database.rows.registries.RowHistoryProviderType` classes.


## `RowHistoryProviderType` hierarchy

Row history is a list of entries generated for an action using `RowHistoryProviderType`-based registry. This base class provides a generic interface needed to fulfill the functionality. Each subclass should implement two elements:

* `RowHistoryProviderType.type` - distinct provider type name, which should match action type that it handles. This means, there's one-to-one mapping between supported action types and row history providers.

* `RowHistoryProviderType.def get_row_history(user: AnyUser, params: ActionData) -> list[RowHistory]:` method. This method will take `baserow.contrib.database.rows.types.ActionData` generic params container, and will extract action type and action params. Note, that some actions are undo/redo-able, which is reflected in `ActionData.action_command_type`. If a row history provider supports undo/redo-able action, it should also account for command type modifier, i.e. for `DO` command type, `UpdateRowsHistoryProvider` will generate a regular, forward field value change:`old value` -> `new value`, while for `UNDO`, the change will be reversed: `new value` -> `old value`. If an action is redone (`REDO` command), the diff will be again of forward type: `old value` -> `new value`.


### `BaseActionTypeRowHistoryProvider` hierarchy

For changes that affect row values changes, including changes to related tables (a set of row create/update/delete/restore actions), there is a dedicated sub-hierarchy based on `baserow.contrib.database.rows.history_providers.BaseActionTypeRowHistoryProvider` class. This class encapsulates field value change diff calculation workflow: whenever an action modifies a row values, the workflow is quite common: 
* get `ActionType` and `ActionType.Params` values from generic `ActionData` container
* get a list of changed rows and before/after values (using `baserow.contrib.database.rows.history_providers.RowChangeData` container).
* for each changed row, generate a list of `RowHistory` entries.
* if there are changes to related tables, process them additionally at the end.

Actions that can provide row history, but they don't modify row values, may use a different workflow and should be implemented using a bare `RowHistoryProviderType` subclass.

`BaseActionTypeRowHistoryProvider` should implement two methods:

* `BaseActionTypeRowHistoryProvider.get_changed_rows(command_type: ActionCommandType, params: ActionType.Params) -> Iterable[RowChangeData]:` - to generate per-row changes
* `BaseActionTypeRowHistoryProvider.get_row_history_entries(user: AnyUser, command_type: ActionCommandType, params: ActionData, action_params: ActionType.Params, row_change: RowChangeData, related_rows_diff: RelatedRowsDiff) -> list[RowHistory]:` - to generate RowHistory entries for a given row values change.

Additionally, a subclass may override `BaseActionTypeRowHistoryProvider.get_related_rows_history(related_rows_diff: RelatedRowsDiff, user: AnyUser,params: ActionData) -> Iterable[RowHistory]:` method to customize (or prevent) generation of related rows history entries. 


## `ActionType.Params` requirements

Each action, that is handled by a `RowHistoryProviderType` subclass, should store necessary context of the change in its `ActionType.Params` dataclass, i.e.: if the action changes a row, it should store: row id, row values before and after change and a map of field metadata (field names and types) for fields that have been changed.

**Note:** `ActionType.Params` is stored in ment to be serialized, so no live objects should be stored (it is stored in the database). Also, mind that when a dict is stored in the database, keys are converted to `str`. This can be handled on the fly in `RowHistoryProviderType` subclass, or in `ActionType.serialized_to_params()`. 

## Row history processing workflow

* An action sends `action_done` signal when it finished processing.
* `baserow.contrib.database.rows.history.on_action_done_update_row_history` handles the signal. This is an entry point of handling row history. 
* The function takes `ActionType.type` and checks for accompanying `RowHistoryProviderType` in `row_history_provider_registry` registry. If there is no class in the registry, processing ends here.
* `RowHistoryHandler.record_history_from_rows_action()` is called. This method calls `RowHistoryProviderType.get_row_history()` method. Received `RowHistory` list is saved to the database and `rows_history_updated` signal is emitted for each table affected. 

## RowHistory Vue components

Row history is presented in `modules/database/components/row/RowHistorySidebar.vue` component, using `modules/database/components/row/RowHistoryEntry.vue` to display single entry. If an entry contains value changes, each change will be rendered with field type-specific sub-component. 



