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

    @property
    def data_provider_registry(self):
        return database_data_provider_type_registry

    def range(self, service: Service) -> tuple[int, int | None]:
        # Nothing dispatched by a button click is a paginated list service.
        return 0, None

    @property
    def is_publicly_searchable(self) -> bool:
        # Button fields are absent from public views, so no anonymous caller
        # reaches this context. Same for every hook below.
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
