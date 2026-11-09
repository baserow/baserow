from typing import Any, Callable, Iterable

from django.contrib.auth.models import AbstractUser

from baserow.core.models import Application, Workspace
from baserow.core.registry import Instance, Registry
from baserow.core.services.registries import ServiceType


class ServiceFilterTargetType(Instance):
    """
    An object owning a Local Baserow service whose filters can be changed, like a
    builder data source. ``type`` is the ``kind`` clients pass to point at one.
    """

    application_type: str
    """The type of the applications holding these objects."""

    read_operation_type: str
    """The operation the user needs to read the object."""

    update_operation_type: str
    """The operation the user needs to change the object."""

    list_operation_type: str
    """The operation filtering the objects the user can list."""

    supports_filter_groups: bool = True
    """Whether the object's filter form can show and edit filter groups."""

    def get_owner(self, owner_id: int) -> Any:
        """
        Returns the object owning the service.

        :param owner_id: Its ID.
        :raises ServiceFilterTargetDoesNotExist: When it doesn't exist or is trashed.
        """

        raise NotImplementedError

    def get_workspace(self, owner: Any) -> Workspace:
        """Returns the workspace the object belongs to."""

        raise NotImplementedError

    def get_name(self, owner: Any) -> str:
        """Returns a name to show for the object."""

        return owner.name

    def get_location(self, owner: Any) -> str:
        """Returns where the object is, e.g. the name of its page."""

        raise NotImplementedError

    def list_owners(self, user: AbstractUser, application: Application) -> Iterable:
        """
        Returns the objects of the application the user can list, filterable or
        not.
        """

        raise NotImplementedError

    def get_filters_unsupported_reason(self, owner: Any, service: Any) -> str | None:
        """
        Returns why the filters of the object's filterable service can't be
        changed, e.g. because its editor doesn't show them, or None when they can.
        """

        return None

    def get_formula_check(
        self, user: AbstractUser, owner: Any
    ) -> Callable[[str], str | None] | None:
        """
        Returns a function telling why a formula can't be a filter value of the
        object, or None when it can. Returns None when filter values can only be
        raw values.
        """

        return None

    def describe_formula_values(self) -> str:
        """Explains which data the object's filter formulas can read."""

        return "Filter values can't be formulas here. Only use raw values."

    def persist(
        self,
        user: AbstractUser,
        owner: Any,
        service_type: ServiceType,
        values: dict[str, Any],
    ) -> None:
        """
        Saves the new filters through the object's undoable update action.

        :param user: The user on whose behalf the filters are saved.
        :param owner: The object.
        :param service_type: The type of its service.
        :param values: The `filter_type`, `service_filters` and
            `service_filter_groups` service values.
        """

        raise NotImplementedError


class ServiceFilterTargetTypeRegistry(Registry[ServiceFilterTargetType]):
    name = "service_filter_target"


service_filter_target_type_registry = ServiceFilterTargetTypeRegistry()
