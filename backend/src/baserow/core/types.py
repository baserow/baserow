from typing import TYPE_CHECKING, Any, NamedTuple, Optional, TypedDict, Union

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser  # noqa: F401

    from baserow.contrib.builder.models import Builder
    from baserow.contrib.dashboard.models import Dashboard
    from baserow.contrib.database.models import Database, Table

# A scope object needs to have a related registered ScopeObjectType
ScopeObject = Any

# A context object can be any object
ContextObject = Any

# A subject needs to have a related registered SubjectType
Subject = Any


# An actor is an object that can do an operation. For now only AbstractUser or Token
Actor = Any

# Objects which can be exported and imported in a `SerializationProcessorType`.
SerializationProcessorScope = Union["Database", "Table", "Builder", "Dashboard"]


class PermissionCheck(NamedTuple):
    original_actor: Actor
    operation_name: str
    context: Optional[ContextObject] = None

    @property
    def actor(self) -> Actor:
        from django.contrib.auth.models import AnonymousUser

        return self.original_actor or AnonymousUser


class PermissionObjectResult(TypedDict):
    name: str
    permissions: Any


Email = str
UserEmailMapping = dict[Email, "AbstractUser"]
