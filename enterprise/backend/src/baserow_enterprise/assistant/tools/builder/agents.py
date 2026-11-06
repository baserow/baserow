"""
Sub-agents for the builder assistant tools.

Contains:
- ``repair_builder_formula_errors()``: Generates what the shared formula step left.
"""

from typing import TYPE_CHECKING

from django.utils.translation import gettext as _

from loguru import logger

from baserow.contrib.builder.pages.models import Page
from baserow.core.exceptions import PermissionException
from baserow.core.tools import ToolContext
from baserow.core.tools.errors import PERMISSION_DENIED_MESSAGE
from baserow_enterprise.assistant.tools.shared.agents import get_formula_generator
from baserow_enterprise.builder.tools.formulas import (
    BuilderFormulaContext,
    BuilderFormulaError,
    current_record_of,
    page_formula_context,
    page_read_from,
    write_builder_formulas,
)
from baserow_enterprise.builder.tools.types import (
    DataSourceUpdate,
    ElementUpdate,
)

from .prompts import BUILDER_FORMULA_PROMPT

if TYPE_CHECKING:
    from baserow_enterprise.assistant.deps import ToolHelpers


# An entry of ``formula_errors`` for a value the model left out.
NO_VALID_FORMULA = "No valid formula was generated."


def _repair_status(entry: BuilderFormulaError) -> str:
    source, item = entry.source, entry.item
    if isinstance(item, DataSourceUpdate):
        return _("Generating formulas for data source %(id)d...") % {"id": source.id}
    if isinstance(item, ElementUpdate):
        return _("Generating formulas for element %(id)d...") % {"id": source.id}
    if entry.kind == "data_source":
        return _("Generating formulas for data source '%(name)s'...") % {
            "name": item.name
        }
    if entry.kind == "element":
        return _("Generating formulas for element '%(ref)s'...") % {"ref": item.ref}
    ref = (
        item.element
        if isinstance(item.element, str)
        else f"element_{source.element_id}"
    )
    return _("Generating formulas for action on '%(ref)s'...") % {"ref": ref}


def repair_builder_formula_errors(
    tool_context: ToolContext,
    tool_helpers: "ToolHelpers",
    page: Page,
    formula_errors: list[BuilderFormulaError],
) -> list[BuilderFormulaError]:
    """
    Generate the values the shared formula step left, one model call per item, each
    item written in its own transaction. No transaction is held across a model call.

    :param tool_context: Who the values are written for.
    :param tool_helpers: Helpers for status updates and the request model profile.
    :param page: The page of the items.
    :param formula_errors: The entries ``apply_builder_formulas`` returned.
    :return: The entries that are still not stored. A value the model left out has
        ``NO_VALID_FORMULA`` as its error.
    """

    by_item: dict[tuple[str, int], list[BuilderFormulaError]] = {}
    remaining: list[BuilderFormulaError] = []
    for entry in formula_errors:
        if not entry.can_repair:
            remaining.append(entry)
        else:
            by_item.setdefault((entry.kind, entry.source.id), []).append(entry)
    if not by_item:
        return remaining

    try:
        generate_formulas = get_formula_generator(
            BUILDER_FORMULA_PROMPT, tool_helpers.model_profile
        )
    except Exception as exc:
        # The items are created, so they are still reported.
        logger.exception("Failed to prepare formula generation: {}", exc)
        for entries in by_item.values():
            for entry in entries:
                entry["error"] = str(exc)
                remaining.append(entry)
        return remaining

    contexts: dict[int, BuilderFormulaContext] = {}
    for entries in by_item.values():
        first = entries[0]
        formulas = {entry["field"]: entry["formula"] for entry in entries}
        tool_helpers.update_status(_repair_status(first))
        denied = False
        try:
            read_from = page_read_from(page, first.kind, first.source)
            if read_from.id not in contexts:
                contexts[read_from.id] = page_formula_context(read_from)
            context = contexts[read_from.id]
            with (
                current_record_of(context, first.kind, first.source),
                context.scope_to_current_record(),
            ):
                # Everything here was refused or is a description, so the model
                # gets it as it is, even when it looks like a formula.
                generated = generate_formulas(formulas, context)
            if generated:
                write_builder_formulas(
                    tool_context.user, first.kind, first.source, first.item, generated
                )
        except PermissionException:
            denied = True
            error, generated = PERMISSION_DENIED_MESSAGE, {}
        except Exception as exc:
            logger.exception(
                "Failed to generate formulas for {} {}: {}",
                first.kind,
                first.source.id,
                exc,
            )
            error, generated = str(exc), {}
        else:
            error = NO_VALID_FORMULA
        for entry in entries:
            if entry["field"] not in generated:
                entry["error"] = error
                entry.permission_denied = denied
                remaining.append(entry)
    return remaining
