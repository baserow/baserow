"""
What a builder formula can read where it is used: the data sources, page parameters
and form inputs of its page, and the row of the repeat or table around it. A caller
that knows this passes it to formula validation, and each data provider uses it to
refuse a path that names something the page doesn't have. Validation without it, as
in the REST API, only checks what a provider can check alone.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from baserow.core.formula.exceptions import InvalidRuntimeFormula
from baserow.core.formula.literals import MAX_LISTED_NAMES

# The key of the path context in a formula ``validation_context``.
PATH_CONTEXT_KEY = "builder_path_context"


class FormulaPathNotReadable(InvalidRuntimeFormula):
    """A path a formula reads that its page, or the place on it, doesn't have."""


def full_path(provider: str, path: list[str]) -> str:
    """The path a formula reads, with its data provider: ``provider.a.b``."""

    return ".".join([provider, *path])


@dataclass
class FormulaPathContext:
    """
    :param page_shared: Whether the formula is on the shared page.
    :param data_sources: The data sources the page can read, by ID, as a dict with
        their ``name`` and ``schema`` (None when it is unknown).
    :param page_parameters: The names of the page's parameters.
    :param form_inputs: The names the page's form inputs are read by.
    :param current_record: The data source of the repeat or table around the
        formula, or None outside one or when it reads a schema property instead.
    :param in_collection: Whether the formula is inside a repeat or a table.
    :param in_unbound_collection: Whether that repeat or table reads nothing: no
        data source and no schema property.
    :param current_record_is_row: Whether ``current_record`` reads a row of
        ``current_record``'s data source, rather than a value of a row.
    :param allow_previous_action: Whether the formula can read earlier workflow
        actions.
    """

    page_shared: bool = False
    data_sources: dict[int, dict[str, Any]] = field(default_factory=dict)
    page_parameters: list[str] = field(default_factory=list)
    form_inputs: list[str] = field(default_factory=list)
    current_record: Optional[int] = None
    in_collection: bool = False
    in_unbound_collection: bool = False
    current_record_is_row: bool = False
    allow_previous_action: bool = False


def path_context_of(
    validation_context: Optional[dict[str, Any]],
) -> Optional[FormulaPathContext]:
    """The path context a formula is validated in, if the caller gave one."""

    return (validation_context or {}).get(PATH_CONTEXT_KEY)


def listed(names: list[str]) -> str:
    if len(names) > MAX_LISTED_NAMES:
        names = [*names[:MAX_LISTED_NAMES], "..."]
    return ", ".join(names) or "none"


def listed_fields(schema: dict[str, Any]) -> str:
    properties = schema.get("items", schema).get("properties", {})
    return listed([f"{key} ({prop.get('title')})" for key, prop in properties.items()])


def matches_schema(segments: list[str], schema: dict[str, Any]) -> bool:
    """
    Whether a path reads something a JSON schema describes. A field must be named by
    its key: a published page only loads the fields its formulas name as field_<id>.
    """

    if not segments:
        return True
    if schema.get("type") == "array":
        if not (segments[0].isdigit() or segments[0] == "*"):
            return False
        items = schema.get("items")
        return matches_schema(segments[1:], items) if items else True
    properties = schema.get("properties")
    if not properties:
        # An object of unknown shape can hold anything; a plain value holds nothing.
        return schema.get("type") == "object"
    prop = properties.get(segments[0])
    if prop is None:
        # The schema of a file leaves out its thumbnails, which pages can read.
        return segments[0] == "thumbnails" and "is_image" in properties
    return matches_schema(segments[1:], prop)


def data_source_path_problem(
    provider: str,
    path: list[str],
    context: FormulaPathContext,
    check_schema: bool = True,
) -> Optional[str]:
    """
    Why a ``data_source`` or ``data_source_context`` path can't be read, if so.

    :param provider: The provider name, for the message.
    :param path: The path after the provider name.
    :param check_schema: Whether what it reads must be in the data source's schema.
    """

    full = full_path(provider, path)
    data_source_id = path[0] if path else ""
    data_source = (
        context.data_sources.get(int(data_source_id))
        if data_source_id.isdigit()
        else None
    )
    if data_source is None:
        names = [f"{key} ({ds['name']})" for key, ds in context.data_sources.items()]
        return (
            f"'{full}' reads data source '{data_source_id}', which isn't on this "
            f"page. Its data sources: {listed(names)}."
        )
    schema = data_source["schema"]
    if not check_schema or schema is None or matches_schema(path[1:], schema):
        return None
    if schema.get("type") == "array" and not (path[1].isdigit() or path[1] == "*"):
        return (
            f"'{full}' needs a row index after the data source, because it returns "
            f"a list, like data_source.{data_source_id}.0.id."
        )
    return (
        f"'{full}' is not something data source {data_source_id} "
        f"('{data_source['name']}') has. Its fields: {listed_fields(schema)}."
    )


def raise_if_unreadable(problem: Optional[str]) -> None:
    """
    :raises FormulaPathNotReadable: When there is a problem.
    """

    if problem:
        raise FormulaPathNotReadable(problem)
