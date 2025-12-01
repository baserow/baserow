# Undo/Redo Technical Guide

## Actions

A ActionType is a class which defines how to `do`, `undo` and `redo` a particular action
in Baserow. It can freely use Handlers to do the logic, but it almost certainly
shouldn't call any other ActionType's unless it is some sort of `meta` ActionAction if
we ever have one. ActionTypes will be retrieved from a registry given a type and
triggered by `API` methods (
e.g. `action_type_registry.get_by_type(DeleteWorkspaceAction).do(user, 
workspace_to_delete)`).

1. In `backend/src/baserow/core/actions/registries.py` there is a `action_type_registry`
   which can be used to register `ActionType`'s
2. An `ActionType` must implement `do`/`undo`/`redo` methods.
    1. `do` Performs the action when a user requests it to happen, it must also save
       a `Action` model using `cls.register_action`
    2. `undo` Must undo the action done by `do`. It must not save any `Action`
       models.
    3. `redo` Must redo the action after it has been undone by `undo`. It must not save
       any `Action` models.
3. An `ActionType` must implement a `Params` dataclass which it will store any
   parameters it needs to `undo` or `redo` the action in. An instance of this dataclass
   must be provided to `cls.register_action` in the `do` method, and it will be
   serialized to JSON and stored in the `Action` table. When `redo` or `undo` is called
   this `dataclass` will be created again from the json in the `Action` row and provided
   to the function.

## Quick summary of the Action Table

See baserow.core.action.models.Action for more details.

| id (serial) | user_id (fk to user table, nullable) | session (text nullable) |  category (text) | created_on (auto_now_add DateTimeField) | type (text)         | params (JSONB)              | undone_at (nullable DateTimeField) | error (text nullable) |
| ------ | ------ | ------ | ------ | ------ |---------------------|-----------------------------| ------ | ------ |
| 1 | 2 | 'some-uuid-from-client' | 'root' | datetime | 'workspace_created' | '{created_workspace_id:10}' |  null | null |

## ActionHandler and Undo/Redo endpoints

The `ActionHandler` has `undo` and `redo` methods which can be used to trigger an
undo/redo for a user. There are two corresponding endpoints in `/api/user/undo`
and `/api/user/redo` which call the `ActionHandler`. To trigger an `undo` / `redo` we
need three pieces of information:

1. The user triggering the undo/redo, so we can check if they still have permissions to
   undo/redo the action. For example a user might be redoing a deletion of a workspace, but
   if they have been banned from the workspace in the meantime they should be prevented
   from redoing.
2. A `client session id`. Every time a user does an action in Baserow we check the
   `ClientSessionId` header. If set we associate the action with that `ClientSessionId`.
   When a user then goes to undo or redo they also provide this header and we only let
   them undo/redo actions with a matching `ClientSessionId`. This lets us have different
   undo/redo histories per tab the user has open as each tab will generate a
   unique `ClientSessionId`.
3. A `category`. Every time an action is performed in Baserow we associate it with a
   particular category. This is literally just a text column on the `Action` model with
   values like `root` or `table10` or `workspace20`. An actions category describes in which
   logical part of Baserow the action was performed. The `ActionType` implementation
   decides what to set its category to when calling `cls.register_action`. When an
   undo/redo occurs the web-frontend sends the categories the user is currently looking
   at. For example if I have table 20 open, with workspace 6 in the side bar and I press
   undo/redo the category sent will be:

```json
{
  root: true,
  table: 20,
  workspace: 6
}
```

By sending this category to the undo/redo endpoint we are telling it to undo any actions
which were done in:

1. The root category
2. The table 20 category
3. The workspace 6 category

For example, if I renamed table 20, then the table_update action would be in workspace 6
category. If I was then looking at table 20 in the UI and pressed undo, the UI would
send the workspace 6 category as one of the active categories as table 20 is in workspace 6.
Meaning I could then undo this rename. If i was to first switch to workspace 5 and press
undo, the UI would send workspace 5 as the category and I wouldn't be able to undo the
rename of table 20 until I switched back into a part of the UI where the workspace 6
category is active.

## Undo Redo Worked Example

1. User A opens Table 10, which is in Application 2 in Workspace 1.
    1. On page load a ClientSessionId `example_client_session_id` is generated and
       stored in the `auth` store. (its a uuid normally).
    1. The current category for this page is set in the `undoRedo` store to
       be: `{root: true, table_id:10, application_id:2, workspace_id:1}`
1. User A changes the Tables name.
    1. A request is sent to the table update endpoint.
        1. The `ClientSessionId` header is set on the request
           to `example_client_session_id`
    1. The table update API endpoint will
       call `action_type_registry.get(UpdateTableAction).do(user, ...)`
    2. The change is made and a new Action is stored.
        1. UpdateTableAction sets the `category` of the action to be `workspace1`
        1. The `ClientSessionId` is found from the request and the session of the action
           is set to `example_client_session_id`
        1. The `user` of the action is set to `User A`
        1. The old tables name is stored in the `action.params` JSONField to facilitate
           undos and redos.
1. User A presses `Undo`
    1. A request is sent to the `undo` endpoint with the `category` request data value
       set to the current category of the page the user has open obtained from
       the `undoRedo` store (see above).
        1. The `ClientSessionId` header is set on the request
           to `example_client_session_id`
    1. `ActionHandler.undo` is called.
        1. It finds the latest action for `User A` in
           session `example_client_session_id` and in any of the following
           categories `["root", "workspace1", "application2", "table10"]`. These were
           calculated from the category parameter provided to the endpoint.
        1. The table rename action is found as it's session matches, it is in
           category `workspace`, it was done by `User A` and it has not yet been undone (
           the `undone_at` column is null).
        1. It deserializes the parameters for the latest action from the table into the
           action's `Params` dataclass
        1. It calls `action_type_registry.get(UpdateTableAction).undo(user, params,
           action_to_undo)
        1. UpdateTableAction using the params undoes the action
        2. Action.undone_at is set to `datetime.now(tz=timezone.utc)` indicating it has now been undone

## What happens when an undo/redo fails

Imagine a situation when two users are working on a table at the same time, in order
they:
1 User A changes a cell in a field called 'date'

2. User A changes a cell in a field called 'Name'
3. User B deletes the 'name' field
4. User A presses 'undo' - in our current implementation they get an error saying the
   undo failed and was skipped
5. User A presses 'undo' - in our current implementation Users A's first change now gets
   undone

We cannot undo User A's latest action as it was to a cell in the now deleted field '
name'. What will happen when is:

1. We will attempt to undo User A's action by calling ActionHandler.undo
2. It will crash and raise an exception
3. In the ActionHandler.undo method we catch this exception and:
    1. We store it on the action's error field
    2. We mark the action as `undone` by setting it's `undone_at` datetime field
       to `datetime.now(tz=timezone.utc)`
    3. We send a specific error back to the user saying the undo failed, and we skipped
       over it.

Interestingly, if the user then presses redo twice we will:

1. Redo user A's first action
2. Now we are trying to redo the action that failed. It has an error set. We see this
   error and send and error back to the user saying `can't redo due to error, skipping.`
3. However we also remove the error and mark the action as "redone".
4. Now the user can press "undo" again and the action will be attempted to be undone a
   second time just like the first. If User B has by this point restored the delete
   field it could now work!
