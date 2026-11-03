from dataclasses import dataclass, field
from typing import Any, Callable

from baserow.core.tools.errors import item_error_message


def _phase_formula_errors(kind: str, phase: dict[str, Any]) -> list:
    return phase.get("formula_errors", [])


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

    after_phase: Callable[[str, dict[str, Any]], list] = _phase_formula_errors
    """Called by ``setup_page`` when a phase is saved, with what the phase created
    ("data_source", "element" or "action") and its result. Returns the
    ``formula_errors`` to report for that phase."""
