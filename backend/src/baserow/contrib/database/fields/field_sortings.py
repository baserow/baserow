import re
from dataclasses import dataclass
from typing import Any, Dict, List, NamedTuple, Optional

from django.db.models.expressions import OrderBy

from baserow.contrib.database.fields.exceptions import OrderByFieldNotFound
from baserow.contrib.database.fields.utils import get_field_id_from_field_key
from baserow.core.utils import split_comma_separated_string

DEFAULT_SORT_TYPE_KEY = "default"


class ParsedOrderEntry(NamedTuple):
    raw: str
    field_key: Any
    direction: str
    sort_type: str


def parse_order_string(
    order_string: str,
    *,
    user_field_names: bool = False,
    field_name_parser=None,
) -> List[ParsedOrderEntry]:
    """
    Parses a comma-separated ``field_X[type]`` order string into structured
    entries without model validation. Callers apply their own capability
    checks (``check_can_order_by`` or ``check_can_group_by``).

    :param order_string: e.g. ``"-field_1[default],field_2"``
    :param user_field_names: When True, treat entries as literal field names
        instead of field-key IDs.
    :param field_name_parser: Callable that strips prefixes from a raw entry
        to extract the field name. Required when ``user_field_names=True``.
    :raises OrderByFieldNotFound: When the string cannot be split.
    :return: List of parsed entries.
    """

    try:
        raw_fields = split_comma_separated_string(order_string)
    except ValueError:
        raise OrderByFieldNotFound(order_string)

    entries = []
    for raw in raw_fields:
        if user_field_names:
            field_key = field_name_parser(raw) if field_name_parser else raw
        else:
            field_key = get_field_id_from_field_key(raw, strict=False)

        direction = "DESC" if raw[:1] == "-" else "ASC"
        type_match = re.search(r"\[(.*?)\]", raw)
        sort_type = type_match.group(1) if type_match else DEFAULT_SORT_TYPE_KEY

        entries.append(
            ParsedOrderEntry(
                raw=raw, field_key=field_key, direction=direction, sort_type=sort_type
            )
        )

    return entries


def serialize_sort_to_string(sort_or_group_by) -> str:
    """
    Serializes a ViewSort or ViewGroupBy instance back into the
    ``field_X[type]`` transport format.
    """

    prefix = "-" if sort_or_group_by.order == "DESC" else ""
    suffix = (
        f"[{sort_or_group_by.type}]"
        if sort_or_group_by.type != DEFAULT_SORT_TYPE_KEY
        else ""
    )
    return f"{prefix}field_{sort_or_group_by.field_id}{suffix}"


def serialize_sorts_to_string(sorts) -> str:
    """
    Serializes an iterable of ViewSort/ViewGroupBy instances into a
    comma-separated ``field_X[type]`` string.
    """

    parts = [serialize_sort_to_string(s) for s in sorts]
    return ",".join(parts) if parts else ""


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
