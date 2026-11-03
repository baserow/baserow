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

    defer_required_formulas: bool = False
    """Create an item whose value to run isn't a usable formula, with a placeholder,
    and report the value in ``formula_errors`` for the caller to fill."""

    item_error: Callable[[Exception], str] = item_error_message
    """The message for an item that failed. It may raise to stop the call."""
