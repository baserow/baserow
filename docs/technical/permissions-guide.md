# 🔐 Permissions system guide

The permission system is used to control access to resources or functionality within
Baserow. It determines who is allowed to perform certain operations or access certain
data.

The permission system is pluggable and allows for the easy addition or replacement of
different components that handle the authorization of user operations.
It provides flexibility and modularity in the way that access to resources or
functionality is controlled within Baserow.

This allows for different authorization strategies to be easily implemented and
swapped out as needed without having to make significant changes to the overall code.

## 📖 Glossary

Before going any further, we need to agree on the definition of some terms:

**Object**: represents a piece of data in Baserow. One of Field, Row, Table, Database,
  Workspace, User, Team, Role, Webhook, …

**Hierarchical Objects**: in Basrow, *Objects* are related to each others and we
can have a parent <-> children dependency between two *Objects*. A full
hierarchy tree can be created with all the Baserow objects. For instance, The
`Table` *Object* is a child of a `Database`.

**Actor**: A generic term grouping anything that can perform *Operations* on an
*Object* in Baserow. Can be a `User` but also a `Personal API Token` or an
`AnonymousUser`...

**Operation**: an action an *Actor* do on an *Object*. Some examples:

- `database.list_tables`: the operation to list the `Tables` related to a `Database`.
- `database_table.create_row`: the action to create a `Row` in a `Table`.
- `database_table.update`: the action to update a `Table` *Object*.

**Context**: the `Object` on which the an *Operation* is applied. For instance:

- for the *Operation* `database.list_tables` the context object is the
  `Database` we want the `Table` list for.
- for the *Operation* `database_table.create_row` the context object is the
  `Table` we want to create the `Row` for.
- for the *Operation* `database_table.update` the context object is also the
  `Table` we want to update.

**Permission request**: a *Permission request* is represented by a triplet
consisting of an *Actor*, an *Operation*, and a *Context*, which is used to
determine if access to a specific resource or functionality is granted or denied
by the *Permission system*. The *Context* can be omitted if the *Operation*
doesn't need one.

**Permission system**: the whole mechanism in Baserow that decides if a
*Permission request* is allowed or not. The *Permission system* relies on
*Permission managers* to take a decision regarding a specific *Permission
request* in a given *Workspace*.

**Permission manager**: a *Permission manager* is a pluggable part of the
*Permission system* that can decide if a *Permission Request* is allowed or not
when some criteria are met. Each *Permission manager* is responsible to take a
decision in some situation. For instance the `StaffOnlyPermissionManager` can
decide to disallow an *Operation* if the given *Actor* is not part of the staff.

**Workspace**: An *Operation* can take place in a specific *Workspace* (Formerly
Group).

**Subject**: includes all *Actors* but also groups of *Actors* like `Teams`.

**Personal API Token**: An authentication token which can be created by users in
their settings area in Baserow. It is owned by a `User`, for a *Workspace*,
allowing access to some of our API endpoints.

## 📃 Main principles

For every *Operation* an *Actor* wants to perform on a *Context*, a *Permission
request* is checked by the permission system. Behind the scene, the *Permission
request* is tested by each *Permission manager* one by one always in same order.
Each *Permission manager* can:

- Allow the Permission Request. Then the operation can be executed.
- Disallow the Permission Request. The operation is canceled and an error is
  raised.
- Passthrough the Permission Request. The Permission Request is then tested by
  the next *Permission manager*

If none of the Permission managers have allowed or disallowed the Permission,
then the permission is disallowed by default.

![Permission diagram](https://raw.githubusercontent.com/baserow/baserow/refs/heads/master/docs/assets/diagrams/permissionProcessus.jpg)

[source](https://viewer.diagrams.net/?tags=%7B%7D&highlight=0000ff&edit=_blank&layers=1&nav=1#R7VnZVtswEP2aPNLjJXbIIwESKEvbAxR4FLZiq5GtVFYW9%2Bs7iiXvJUkhUCgvOZrxWMvcO4uVjn0YLUccTcML5mPasQx%2F2bGPOpbVd7rwKxVppnBNO1MEnPiZyiwUV%2BQXVkpDaWfEx0nFUDBGBZlWlR6LY%2ByJig5xzhZVszGj1VWnKMANxZWHaFN7S3wRZtp9q1foTzAJQr2y6fazJxHSxuokSYh8tiip7OOOfcgZE9koWh5iKn2n%2FXJ7mt7S84k7%2Bvwt%2BYluBmfXl9%2F3ssmG27ySH4HjWDzv1FY29RzRmfKXOqtItQM5m8U%2BlpMYHXsQiojC0IThDyxEqgBHM8FAxbgIWcBiRM8Zmyq7MYuFMjOljGP%2FQAIL8gNl3iRTDQmlag2QlP0%2BSIngbJJjJyfIgZDGFD1gOkDeJFht9JBRxuFRzGIsp%2FKBDOosxeaOC%2B1gQ98qDBI24x5%2BxE4Fh0A8wI%2FN52Z2cn8lnirkRphFWPAUDDimSJB5lcxIxUSQ2xW4w0BBvwUN7AYNRrBmLJeSzsE8IklCWPwIOSQwi5AIfDVFKw8tIJ1UCVMmApx1EFCUJArGNShvh9Icc4GXj%2FpVPbUNFdypljNxUaQKU8d%2FWEoTXWNHSHRbAtKlsOrAJ3MYBnJ4ybQS1ijpP2L3SbHrbhi7urStDV5Fsj3jk%2BM4boVomlQbx7ea%2FSsjcNbChI3HCWy2Trt8E3%2FPRKfBxHuo43WGrQfpTXPwlRjW25BgabXX%2BnfJ5DbIdJpIR4S4Vl%2Bgi0SxALpYxkOaW3gzvkKgZhuhGNo3DqOOPWwmv5BFD7NkfV2q8EGybYgiQqVvTzCdY0E81FK9ECVBDIIHG4M9tBINliRxAJJbSNcrYkOi311Vs%2FrVqmb2Wspat6Wsmeau6lqvQYDrFbIMAAXOruAkkhKIUraQ%2BL%2BzTqNbw8QynFduNfYbkMi%2B4qODeEJ%2B1%2BGzvoUwt24hrDfWP%2FQ%2F%2BodX5Jf13joIvcMNWgifJHkV%2BegMqt%2B7Zu1712ypQkZLFdp%2FhirEjfDCvDm4pQejL2dWgnu20dc3UE9ICa1B35IcSriCV3l6l4c7CPdS%2BORo8WhZfniUamlJxF1pXHoLpOIlKeh3njsF6EvUF79hWr0KmROlJYOpTABJS0bQrahbJVy3V7ulXGNvWU6NYtkOnje36DgqcssVpvI2WueXGC%2F%2F%2FPXxzjrV%2Bp1Yt7thp%2BrsqlPV1Wz910M59b8zWJz6VaX9gh8Qram7GTXXaILzmBkTnvy3QZMX0R2gA2Lxr1OWA4u%2F7uzj3w%3D%3D)

Example:

1) If a non admin user wants to create `Table` in a `Database` of his
`Workspace`, the following permission is tested:
`(user, "database.create_table", database)` by the Permission system. 2) The
Permission request is first given to the `CorePermissionManager` that can't take
a decision, because it's not a core operation. Then it is given to the
`StaffOnlyPermissionManager` that also can't decide because this is not a staff
only operation. 3) The last permission manager the permission will be tested is
the `BasicPermissionManager` that will allows the Permission request because
it's not an Admin only operation so the user can execute it.

## ⚙️ The backend

Most of the Permission system is driven by the backend. The main components of
the Permissions system are the following:

- `OperationType`: you need an `OperationType` for every *Operation* you want to
  check.
- `PermissionManagerType`: the *Permission managers* are responsible for
  allowing or not the Permission requests.
- `SubjectType`: every *Actor* you want to use in the *Permission system* must
  belongs to a `SubjectType`.
- `ObjectScopeType`: every *Context* object must be part of the Baserow *Object*
  hierarchy. By now it's implemented by having a related `ObjectScopeType` for
  each *Object* type.

All of them are objects you can register in their related registry to extend the
core functionnalities of Baserow Permission system.

### Check a Permission on the backend

When you want to test a permission on the backend, you'll have to use the
`CoreHandler.check_permission` method.

```python
CoreHandler().check_permission(
    # The actor can be the user who did the request: actor = request.user.
    actor, 
    # CreateRowDatabaseTable is an `OperationType` class and `.type` is its name.
    CreateRowDatabaseTable.type,  
    context=table, 
    workspace=workspace
)
```

If the permission request is allowed then this method will return `True` if not,
it will raise a `PermissionException`.

The workspace (formerly known as a group) is optional if the operation is a core 
operation that does not belong to any specific workspace.

### Filter a Django Queryset

Another common use case related to permissions is to filter a django queryset
based on the permissions of the user. You can acheive queryset filtering with
this method call.

```python
CoreHandler().filter_queryset(
    # The actor can be the user who did the request: actor = request.user.
    actor, 
    # CreateRowDatabaseTable is an `OperationType` class and `.type` is its name.
    ListTablesDatabaseTableOperationType.type,  
    queryset,
    workspace=workspace
)
```

Here the context is the database because we are listing the tables of this
database but the queryset is a `Table` queryset. This is consistent with the
`object_scope` property of the `ListTablesDatabaseTableOperationType` which is
`TableObjectScope`. This is the purpose of `object_scope` property it helps to
determine what kind of objects the operation targets.

### Declare a new operation

An `OperationType` instance must be registered for each Operation you want to
check. It can be declared this way:

```python
from baserow.core.registries import OperationType

class ListTablesDatabaseTableOperationType(OperationType):
    type = "database.list_tables" # Type
    context_scope_name = "database" # The name of the type of context needed to check permissions
    object_scope_name = "database_table" # The name of the type of the objects handled by the operation
```

For most of the operation the `context_scope_name` and the `object_scope_name`
are the same, so the last can be omitted. However regarding all "list"
operations, the object_scope_name is in general one of the children of the
context object in the hierarchy of the *Objects*. When you want to list all
`Tables` of a `Database`, the context is a `Database` and the objects are the
`Tables`. When you list all `Databases` of an `Application`, the context is an
`Application` and the objects are the related `Databases`.

This class must be registered in the `operation_type_registry` in order to be
used.

```python
from baserow.core.registries import operation_type_registry
operation_type_registry.register(ListTablesDatabaseTableOperationType())
```

An `Operation` instance is saved in database for each registered operation.
You can use them later in your permission manager code if necessary.

### Create a backend Permission manager

A permission manager is responsible for deciding whether or not a Permission
Request is allowed for a certain application area. To ensure proper separation
of concerns, a good permission manager should only handle one permission
checking use case. The permission managers are then stacked to create a complex
and powerful permission checking algorithm. You can think of them like being a
Django middleware, but instead for a Permission Request instead.

To create a new permission manager you have to create a new
`PermissionManagerType` and implement the required methods.

```python
from baserow.core.registries import PermissionManagerType

class OwnedTablePermissionManagerType(PermissionManagerType):
    type = "owned_table"

    def check_multiple_permissions(self, check, workspace=None, include_trash=False):
        ...

    def get_permissions_object(self, actor, workspace=None):
        ...

    def filter_queryset(self, actor, operation_name, queryset, workspace=None)
        ...
```

A quick summary of these methods:

- `.check_multiple_permissions` is the permissions checking method itself. It
  takes multiple checks at once for better performances. For each check the
  result dict should have the value `True` if the permission manager can accept
  the permission or an instance of `PermissionException` if not or it shouldn't
  include the check at all if the permission manager cannot make a decision
  about this check.
- `get_permissions_object` should return any value that will be helpfull to the
  frontend permission manager to check a frontend permission. The data returned
  should be sufficient for the frontend to make a decision without having to
  request further data from the backend.
- `filter_queryset` is used to filter a queryset regarding the permissions the
  actor has on the Objects returned by the queryset. The method should exclude
  the same Objects that the `.check_permission` would exclude if it was called
  for each Objects of the queryset.

You can read the related docstring to learn more about these methods.

Then, you can register it in the `permission_manager_type_registry`.

```python
from baserow.core.registries import permission_manager_type_registry
permission_manager_type_registry.register(OwnedTablePermissionManagerType())
```

You'll have to add your permission manager in the enabled permission manager
list in the Django settings:

```python
PERMISSION_MANAGERS = [
'core',
'staff_only',
...
'owned_table', # <- here
...
'basic'
]
```

The position of the permission manager in the list depends on its priority over
the other permission managers. In our case we want the permission manager to
answer before the basic permission manager has a chance to refuse it.

Now you can check a permission that is handled by your permission manager 🎯.

Remember that you probably need a frontend permission manager for each backend
permision manager. See frontend section for more information.

## 📺 The frontend

### How to check a Permission

On the frontend you can check a permission with the `$hasPermission` method
available on the Vue instance:

```js
// Inside a Vue component
// this.$hasPermission(<operationName>, <contextObject>, <currentWorkspaceId>)
this.$hasPermission("database.create_table", database, workspace.id);
```

This call returns `true` if the operation is granted `false` otherwise.

### The permissions object

The frontend permissions are calculated with the permission object sent by the
backend at login for each workspace the user has access to. Check the
`.get_permissions_object` method from each backend permission manager.

The permission object looks like this:

```json
[
  {
    "name": "core",
    "permissions": [
      "list_workspaces"
    ]
  },
  {
    "name": "staff",
    "permissions": {
      "staff_only_operations": [
        "settings.update"
      ],
      "is_staff": true
    }
  },
  {
    "name": "basic",
    "permissions": {
      "admin_only_operations": [
        "workspace.list_invitations",
        "...",
        "workspace.delete"
      ],
      "is_admin": true
    }
  }
]
```

Each entry of the list has been generated by a permission manager on the
backend. The `name` property is the `.type` of the permission manager itself and
the `permissions` property can be any value that helps the frontend to decide of
the permission can be granted or not. For each backend permission manager a
frontend permission manager should also be registered to handle it's value.

To check the permissions, the frontend `$hasPermission` plugin asks to each
permission manager for which the name is listed in this object, in the list
order, if the permission is granted or not given the data from the `permissions`
property.

For instance the
`BasicPermissionManagerType.hasPermission(permissions, operation, context, workspaceId)`
method will be called with the following object:

```json
{
    "admin_only_operations": [
    "workspace.list_invitations",
    "...",
    "workspace_user.delete"
    ],
    "is_admin": true
}
```

See next section to learn how to create the frontend permission manager.

### Creating a permission manager

For each backend permission manager you probably need a frontend permission
manager (some permission managers don't need one).

You can create a frontend permission manager this way:

```js
import { PermissionManagerType } from '@baserow/modules/core/permissionManagerTypes'


export class OwnedTablePermissionManagerType extends PermissionManagerType {
  static getType() {
    return 'owned_table'
  }

  hasPermission(permissions, operation, context) {
    // ...
  }
}
```

Check out the documentation of the `PermissionManagerType` methods to figure out
how to implement `hasPermission` for your permission manager.

Then you need to register it during the Vue plugin initialisation phase in the
`plugin.js` frontend file of your project.

```js
app.$registry.register('permissionManager', new OwnedTablePermissionManagerType(context))
```

And that's it, you have a fully functionnal frontend permission manager.

## 📝 Conclusion

If you want to create a new way to validate Permissions, you'll have to:

- [ ] Create a backend permission manager
- [ ] Implement its methods
- [ ] Register the permission manager
- [ ] Add missing operations if any
- [ ] Create a frontend permission manager
- [ ] Implement its methods
- [ ] register the frontend permisison manager
- [ ] Test everything

## 🤔 A few considerations

The Permission system has been designed with these constraints in mind:

- Must be extensible (to support RBAC from enterprise folder)
- Must be as much compatible with the previous system (The `.has_user` method)
  as possible
- Must play well with realtime
- Must be able to work with object but also a collection of objects
- Must be performant
- Must avoid code duplication between backend and frontend

That may explain some of the decisions that has been made.

**More technically**:

- The parent of a `Database` is not the workspace has we could imagine first but the
  "more generic" type which is the `Application`. It solves a lot of issues (but
  also creates some if we don't pay attention).
- For a `User` Actor, the Basic permission manager has two "roles", `ADMIN` and
  `MEMBER` which is compatible with the previous permission system. The Role
  name is stored in the `WorkspaceUser.permissions` field. The idea is to make the
  other Role based system using this field to make them compatible and avoid
  duplication of data or synchronisation when switching from one system to
  another. For the `BasicPermissionManagerType`, The `ADMIN` value in this
  property means the user is `ADMIN`. For any other values the `User` is treated
  as a simple `MEMBER` of the Workspace.
- The current Personnal API Token has been partially migrated to the current
  permission system.
- The `AnonymousUser` is a `SubjectType` that can be handled by some permission
  manager.

**TBD**:

- Add a new Authentication Token to replace the old one that really use the
  permission system.
- Renaming the `.permissions` field to something more understantable.
- Handle Public views with a new Permission manager.
- Create a few more Roles
