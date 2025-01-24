from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from django.db.models import F
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
        Returns the underlying field expression (like "field_1__value")
        of the OrderBy order.

        OrderBy expression for a field is always F(field_expression) or
        Collate(F(field_expression)) or a django Expression that can be
        stringified.
        """

        if self.collation:
            return self.order.expression.source_expressions[0].name
        elif isinstance(self.order.expression, F):
            return self.order.expression.name
        else:
            return str(self.order.expression)

    @property
    def order_bys(self) -> List[OrderBy]:
        return self.order if isinstance(self.order, (list, tuple)) else [self.order]

    @property
    def collation(self) -> str:
        return getattr(self.order.expression, "collation", None)
