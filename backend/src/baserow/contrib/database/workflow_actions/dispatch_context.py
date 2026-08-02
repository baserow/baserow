from typing import Any, Dict, List, Optional

from django.contrib.auth.models import AbstractUser

from baserow.contrib.database.data_providers.registries import (
    database_data_provider_type_registry,
)
from baserow.contrib.database.fields.models import ButtonField
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.models import Service
from baserow.core.services.utils import ServiceAdhocRefinements


class DatabaseDispatchContext(DispatchContext):
    """
    The dispatch context for a button field click.

    It carries the clicked row so actions can read its values, and the acting
    user so Local Baserow services can authorise as the clicker rather than as
    an integration's `authorized_user` (ADR 006 section 5).
    """

    own_properties = ["field", "row"]

    # A click runs as the clicker, so an action that would write a field they
    # cannot write fails the click rather than quietly dropping that field the
    # way the builder's upsert does (ADR 006 section 5). This is the only
    # dispatch context that asks for it.
    requires_writable_fields = True

    def __init__(
        self,
        actor: Optional[AbstractUser] = None,
        field: Optional[ButtonField] = None,
        row: Any = None,
        **kwargs,
    ):
        """
        :param actor: The user who clicked. Nothing in the dispatch path reads a
            request, so the context takes the user directly. Defaults to None
            because the base `clone()` reconstructs the context without
            `actor` and assigns it onto the new instance afterwards; `field`
            and `row` follow suit purely so this stays valid Python (a
            defaulted parameter can't precede a required one), since `clone()`
            always supplies them through `own_properties`.
        :param field: The clicked button field.
        :param row: The clicked row, as a generated table model instance.
        """

        # The defaults above exist only so `clone()` can reconstruct this
        # class without passing `actor`. `field` and `row` are never
        # optional for a real button dispatch, so a caller that forgets one
        # must fail here rather than surface a confusing error later inside
        # a data provider.
        if field is None or row is None:
            raise TypeError("DatabaseDispatchContext requires field and row")

        self.field = field
        self.row = row

        # `actor` is carried through `clone()` explicitly rather than through
        # `own_properties`, so it is deliberately absent from the list above.
        super().__init__(actor=actor, **kwargs)

    @property
    def data_provider_registry(self):
        return database_data_provider_type_registry

    def range(self, service: Service) -> tuple[int, int | None]:
        # Nothing dispatched by a button click is a paginated list service.
        return 0, None

    @property
    def is_publicly_searchable(self) -> bool:
        # Button fields are not exposed in public views at all, so no anonymous
        # caller can reach this context. The same holds for every hook below.
        return False

    def search_query(self) -> Optional[str]:
        return None

    def searchable_fields(self) -> List[str]:
        return []

    @property
    def is_publicly_filterable(self) -> bool:
        return False

    def filters(self) -> Optional[str]:
        return None

    @property
    def is_publicly_sortable(self) -> bool:
        return False

    def sortings(self) -> Optional[str]:
        return None

    @property
    def public_allowed_properties(self) -> Optional[Dict[str, Dict[int, List[str]]]]:
        return None

    def validate_filter_search_sort_fields(
        self, fields: List[str], refinement: ServiceAdhocRefinements
    ):
        raise NotImplementedError(
            "A button dispatch has no ad hoc refinement surface to validate."
        )
