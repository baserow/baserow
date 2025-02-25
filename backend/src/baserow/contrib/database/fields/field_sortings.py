from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from django.db.models.expressions import OrderBy


@dataclass
class OptionallyAnnotatedOrderBy:
    """
    Represents a sorting for a single Baserow field, needed by
    field types "get_order" methods.

    It holds the Django's OrderBy expression to be used in queryset.order() for
    a single field as well as an optional annotation dictionary for an
    annotation on which the order expression depends.

    Field expression (e.g. "field_1__value") and collations are computed from the
    order by expression.
    """

    order: OrderBy | List[OrderBy]
    annotation: Optional[Dict[str, Any]] = None
    can_be_indexed: bool = False

    @property
    def field_expression(self) -> str:
        """
        Returns the underlying field expression (like `Cast("field_1__value")`)
        of the OrderBy order as a string. It can be used to identify the uniqueness of
        a sort for indexing purposes, for example.
        """

        return str(self.order.expression)

    @property
    def order_bys(self) -> List[OrderBy]:
        return self.order if isinstance(self.order, (list, tuple)) else [self.order]

    @property
    def collation(self) -> str:
        return getattr(self.order.expression, "collation", None)
