from typing import Any, Optional

from django.contrib.auth.models import AbstractUser

from baserow.contrib.database.data_providers.registries import (
    database_data_provider_type_registry,
)
from baserow.contrib.database.fields.models import ButtonField
from baserow.contrib.database.rows.data_providers import RowDataProviderType
from baserow.contrib.database.workflow_actions.data_providers import (
    PreviousActionDataProviderType,
)
from baserow.core.formula.registries import DataProviderTypeRegistry
from baserow.core.services.dispatch_context import DispatchContext


class DatabaseDispatchContext(DispatchContext):
    """
    The dispatch context for a button field click.

    It carries the clicked row so actions can read its values, and the acting
    user so Local Baserow services can authorise as the clicker rather than as
    an integration's `authorized_user` (ADR 006 section 5).

    Search, filter, sort and pagination stay at the base class defaults: button
    fields are absent from public views, so no anonymous caller reaches this
    context, and nothing dispatched by a click is a paginated list service.
    """

    own_properties = ["field", "row"]

    def __init__(
        self,
        actor: Optional[AbstractUser] = None,
        field: Optional[ButtonField] = None,
        row: Any = None,
        **kwargs,
    ):
        """
        :param actor: The user who clicked. Nothing in the dispatch path reads
            a request, so the context takes the user directly.
        :param field: The clicked button field.
        :param row: The clicked row, as a generated table model instance.
        """

        # Everything defaults to None only so `clone()` can rebuild this class
        # without passing `actor`. Neither `field` nor `row` is optional for a
        # real dispatch, so fail here rather than inside a data provider later.
        if field is None or row is None:
            raise TypeError("DatabaseDispatchContext requires field and row")

        self.field = field
        self.row = row

        # `clone()` carries `actor` over itself, hence its absence from
        # `own_properties`.
        super().__init__(actor=actor, **kwargs)

        # Holds the row read for the action that is running. It has to be made
        # here rather than by the provider: `clone()` copies this cache dict,
        # so a holder added to a clone would be thrown away with it, while the
        # dict placed here is shared by reference with every clone.
        self.cache[RowDataProviderType.CACHE_KEY] = {}

        # Each dispatched action's result, keyed by action id, for the actions
        # after it to read, and the actions themselves so a path can be
        # prepared without another query. Placed here for the same reason as
        # the holder above.
        self.cache[PreviousActionDataProviderType.CACHE_KEY] = {}
        self.cache[PreviousActionDataProviderType.ACTIONS_CACHE_KEY] = {}

    def start_action(self) -> None:
        """
        Drops the row read by the action that just finished, so the next one
        reads the row as it is when it starts (ADR 006 section 4).

        Previous action results are deliberately kept: they are what the rest
        of the sequence chains from.
        """

        self.cache[RowDataProviderType.CACHE_KEY].clear()

    @property
    def data_provider_registry(self) -> DataProviderTypeRegistry:
        return database_data_provider_type_registry
