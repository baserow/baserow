from dataclasses import dataclass, field
from typing import Callable

from baserow.core.tools.errors import item_error_message


@dataclass
class BuilderWriteOptions:
    """
    What a client adds to the builder write tools. These stay off the functions a
    tool wraps, because every parameter there is offered to clients.
    """

    known_refs: dict[str, int] = field(default_factory=dict)
    """Element refs from earlier calls."""

    known_data_source_refs: dict[str, int] = field(default_factory=dict)
    """Data source refs from earlier calls."""

    known_shared_page_refs: set[str] = field(default_factory=set)
    """Which of ``known_refs`` are on the shared page. The call adds the refs of the
    shared page elements it creates."""

    column_name_beats_formula: bool = False
    """A new table column named like a field shows that field, even when it has a
    formula or description of its own."""

    defer_required_formulas: bool = False
    """Create an item whose value to run isn't a usable formula, with a placeholder,
    and report the value in ``formula_errors`` for the caller to fill."""

    item_error: Callable[[Exception], str] = item_error_message
    """The message for an item that failed. It may raise to stop the call."""
