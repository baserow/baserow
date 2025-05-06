# Row History

When an action is performed, it can leave row history entries for rows affected. 

A row history entry stores information on:
* which row has been affected
* what action has been performed
* when it was performed
* who did it
* what has been changed.

Note, that an action can affect multiple rows and, indirectly, related tables/rows. Row history items returned by the action should reflect that.

## Row history handling

Each action sends `action_done` signal when it finished processing. One of signal handlers is `baserow.contrib.database.rows.history.on_action_done_update_row_history` function which checks if the action conforms `baserow.contrib.database.rows.types.ActionHistoryProvider` protocol. Internally, `get_row_change_history()` action's method is called, and returned list of `baserow.contrib.database.rows.models.RowHistory` objects is saved.

## Action row history interface

Action class should implement `get_row_change_history(user: AbstractUser, params: baserow.contrib.database.rows.types.ActionData) -> "list[RowHistory]"` class method. This way it will conform `baserow.contrib.database.rows.types.ActionHistoryProvider` protocol. 

The implementation should take several key points into considerations:

* during action execution:
  + row-specific context (row ids, rows values, fields metadata per row) should be populated in `ActionType.do()` and stored in `ActionType.Params` structure. Values should be serializable. Params object should also distinct between before and after values, if this is important for the context.
* during `get_row_change_history()` call:
  + `params` is a generic container, but it's an entry point to get action params from `prams.params`.
  + `params.type` tells if the action is direct, `undo` or `redo`. This may be important for the context. If action is executed for `undo`/`redo`, the direction of values change may be different.
  + The logic should also detect related fields changes. This can be done by using `baserow.contrib.database.rows.helpers.update_related_tables_entries()` function.
  + each value change should be stored in `RowChangeDiff.before_values`/`RowChangeDiff.after_values` with values specific to field type for a specific field. Also, each value should be stored in serializable format. `FieldType.get_export_serialized_value()` is able to produce such values. 


## RowHistory Vue components

Row history is presented in `modules/database/components/row/RowHistorySidebar.vue` component, using `modules/database/components/row/RowHistoryEntry.vue` to display single entry. If an entry contains value changes, each change will be rendered with field type-specific sub-component. 



