"""
Sub-agents for the builder assistant tools.

Contains:
- ``update_element_formulas()``: Generates formulas for elements.
- ``update_data_source_formulas()``: Generates formulas for data sources.
- ``repair_builder_formula_errors()``: Generates what the shared formula step left.
- ``update_workflow_action_formulas()``: Generates formulas for workflow actions.
"""

from typing import TYPE_CHECKING, Any

from django.db import transaction
from django.utils.translation import gettext as _

from loguru import logger

from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.mixins import CollectionElementTypeMixin
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.workflow_actions.actions import (
    UpdateBuilderWorkflowActionActionType,
)
from baserow.contrib.builder.workflow_actions.handler import (
    BuilderWorkflowActionHandler,
)
from baserow.core.exceptions import PermissionException
from baserow.core.formula import resolve_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.formula.types import BASEROW_FORMULA_MODE_ADVANCED
from baserow.core.services.models import Service
from baserow.core.tools import ToolContext
from baserow.core.tools.errors import PERMISSION_DENIED_MESSAGE
from baserow_enterprise.assistant.tools.shared import raise_if_permission_denied
from baserow_enterprise.assistant.tools.shared.agents import get_formula_generator
from baserow_enterprise.builder.tools.formulas import (
    BuilderFormulaContext,
    BuilderFormulaError,
    current_record_of,
    page_formula_context,
    write_builder_formulas,
)
from baserow_enterprise.builder.tools.types import (
    ActionCreate,
    DataSourceCreate,
    DataSourceUpdate,
    ElementItemCreate,
    ElementUpdate,
)
from baserow_enterprise.tools.formula_utils import (
    formula_object,
    is_valid_formula,
)

from .prompts import BUILDER_FORMULA_PROMPT

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from baserow_enterprise.assistant.deps import ToolHelpers


# An entry of ``formula_errors`` for a value the model left out.
NO_VALID_FORMULA = "No valid formula was generated."

# ---------------------------------------------------------------------------
# Formula update orchestrators
# ---------------------------------------------------------------------------


def _generate_formulas(generate, formulas: dict, context: BuilderFormulaContext):
    """Preserve explicit formulas and scope implicit collection formulas to a row.

    The same list is otherwise advertised twice, once as its first example row
    and once as current_record. Both resolve successfully, but a fixed list
    index repeats the same value on every card. Only the enclosing collection's
    source is scoped; unrelated sources and formulas outside collections remain
    available. Explicit expressions are validated against the complete context.
    """

    if not context._current_record_stack or "current_record" not in context.context:
        return generate(formulas, context)

    generated = {}
    descriptions = {}
    for field, description in formulas.items():
        if is_valid_formula(description):
            resolve_formula(
                formula_object(description, mode=BASEROW_FORMULA_MODE_ADVANCED),
                formula_runtime_function_registry,
                context,
            )
            generated[field] = description
        else:
            descriptions[field] = description
    if descriptions:
        with context.scope_to_current_record():
            generated.update(generate(descriptions, context))
    return generated


def _element_for_update(element: Any) -> Any:
    """
    Load ``element`` again, locked, so writing generated formulas onto it keeps the
    changes made while the model ran.
    """

    return ElementHandler().get_element_for_update(element.id)


def update_element_formulas(
    user: "AbstractUser",
    page: Page,
    elements: list[ElementItemCreate],
    element_mapping: dict[str, tuple[Any, ElementItemCreate]],
    tool_helpers: "ToolHelpers",
) -> list[str]:
    """
    Generate and apply formulas for elements that need them.

    :param user: The user whose element permissions apply.
    :param page: The page containing the elements.
    :param elements: The assistant element definitions to process.
    :param element_mapping: Assistant references mapped to persisted elements.
    :param tool_helpers: Helpers for status updates and the request model profile.
    :return: Formula-generation errors, or an empty list on success.
    """

    errors: list[str] = []
    context = BuilderFormulaContext(page)
    context.load_page_context()
    generate_formulas = get_formula_generator(
        BUILDER_FORMULA_PROMPT, tool_helpers.model_profile
    )

    for el_create in elements:
        ref = el_create.ref
        if ref not in element_mapping:
            continue

        orm_element, _el_create = element_mapping[ref]

        # Push collection context if inside a repeat/table
        pushed = False
        try:
            ancestor = ElementHandler().get_first_ancestor_of_type(
                orm_element, CollectionElementTypeMixin
            )
        except KeyError:
            # Parent element may be on a different page (e.g. shared page header)
            ancestor = None
        if ancestor:
            context.push_current_record_context(ancestor.data_source_id)
            pushed = True
        elif (
            isinstance(
                element_type_registry.get(el_create.type), CollectionElementTypeMixin
            )
            and hasattr(orm_element, "data_source_id")
            and orm_element.data_source_id
        ):
            context.push_current_record_context(orm_element.data_source_id)
            pushed = True

        try:
            formulas = el_create.get_formulas_to_create(orm_element, context)
            if formulas:
                tool_helpers.update_status(
                    _("Generating formulas for element '%(ref)s'...") % {"ref": ref}
                )
                try:
                    generated = _generate_formulas(generate_formulas, formulas, context)
                    if generated:
                        with transaction.atomic():
                            el_create.update_with_formulas(
                                user, _element_for_update(orm_element), generated
                            )
                except Exception as exc:
                    raise_if_permission_denied(exc)
                    logger.error(
                        "Failed to generate formulas for element {}: {}",
                        orm_element.id,
                        exc,
                    )
                    errors.append(f"Formula generation failed for '{ref}': {exc}")
        except PermissionException:
            errors.append(
                f"Permission denied while configuring element '{ref}'. "
                "The element was created, but its formulas were not applied. "
                "Do not retry the denied operation."
            )
        finally:
            if pushed:
                context.pop_current_record_context()

    return errors


def update_data_source_formulas(
    user: "AbstractUser",
    page: Page,
    ds_pairs: list[tuple[Any, DataSourceCreate]],
    tool_helpers: "ToolHelpers",
) -> list[str]:
    """
    Generate and apply formulas for data sources that need them.

    :param user: The user whose data-source permissions apply.
    :param page: The page containing the data sources.
    :param ds_pairs: Persisted data sources paired with assistant definitions.
    :param tool_helpers: Helpers for status updates and the request model profile.
    :return: Formula-generation errors, or an empty list on success.
    """

    errors: list[str] = []
    if not ds_pairs:
        return errors

    context = BuilderFormulaContext(page)
    context.load_page_context()
    generate_formulas = get_formula_generator(
        BUILDER_FORMULA_PROMPT, tool_helpers.model_profile
    )

    for orm_ds, ds_create in ds_pairs:
        try:
            formulas = ds_create.get_formulas_to_create(orm_ds, context)
            if formulas:
                tool_helpers.update_status(
                    _("Generating formulas for data source '%(name)s'...")
                    % {"name": ds_create.name}
                )
                try:
                    generated = generate_formulas(formulas, context)
                    if generated:
                        with transaction.atomic():
                            ds_create.update_with_formulas(user, orm_ds, generated)
                except Exception as exc:
                    raise_if_permission_denied(exc)
                    logger.error(
                        "Failed to generate formulas for data source {}: {}",
                        orm_ds.id,
                        exc,
                    )
                    errors.append(
                        f"Formula generation failed for data source "
                        f"'{ds_create.name}': {exc}"
                    )
        except PermissionException:
            errors.append(
                f"Permission denied while configuring data source '{ds_create.name}'. "
                "It was created, but its formulas were not applied. "
                "Do not retry the denied operation."
            )
        except Exception as exc:
            logger.error(
                "Error processing data source {} for formulas: {}", orm_ds.id, exc
            )
            errors.append(f"Error processing data source '{ds_create.name}': {exc}")

    return errors


def update_workflow_action_formulas(
    user: "AbstractUser",
    page: Page,
    action_pairs: list[tuple[Any, ActionCreate]],
    tool_helpers: "ToolHelpers",
) -> list[str]:
    """
    Generate and apply formulas for workflow actions that need them.

    :param user: The user whose workflow-action permissions apply.
    :param page: The page containing the workflow actions.
    :param action_pairs: Persisted actions paired with assistant definitions.
    :param tool_helpers: Helpers for status updates and the request model profile.
    :return: Formula-generation errors, or an empty list on success.
    """

    errors: list[str] = []
    if not action_pairs:
        return errors

    context = BuilderFormulaContext(page)
    context.load_page_context()
    generate_formulas = get_formula_generator(
        BUILDER_FORMULA_PROMPT, tool_helpers.model_profile
    )

    for orm_action, action_create in action_pairs:
        pushed = False
        try:
            formulas = action_create.get_formulas_to_create(orm_action, context)

            ancestor = ElementHandler().get_first_ancestor_of_type(
                orm_action.element, CollectionElementTypeMixin
            )
            if ancestor:
                context.push_current_record_context(ancestor.data_source_id)
                pushed = True

            if formulas:
                ref = (
                    action_create.element
                    if isinstance(action_create.element, str)
                    else f"element_{orm_action.element_id}"
                )
                tool_helpers.update_status(
                    _("Generating formulas for action on '%(ref)s'...") % {"ref": ref}
                )
                try:
                    generated = _generate_formulas(generate_formulas, formulas, context)
                    with transaction.atomic():
                        # A row action's mappings are replaced as a whole list, so
                        # a concurrent add_action_field_mapping waits for this.
                        service_id = getattr(orm_action, "service_id", None)
                        if service_id is not None:
                            Service.objects.select_for_update().filter(
                                id=service_id
                            ).first()
                        # Loaded again so changes made while the model ran are
                        # kept.
                        fresh_action = (
                            BuilderWorkflowActionHandler().get_workflow_action(
                                orm_action.id
                            )
                        )
                        values = action_create.formula_values(fresh_action, generated)
                        if values:
                            UpdateBuilderWorkflowActionActionType.do(
                                user, fresh_action, **values
                            )
                except Exception as exc:
                    raise_if_permission_denied(exc)
                    logger.error(
                        "Failed to generate formulas for action {}: {}",
                        orm_action.id,
                        exc,
                    )
                    errors.append(
                        f"Formula generation failed for action on '{ref}': {exc}"
                    )
        except PermissionException:
            errors.append(
                f"Permission denied while configuring action on '{action_create.element}'. "
                "The action was created, but its formulas were not applied. "
                "Do not retry the denied operation."
            )
        except Exception as exc:
            logger.error(
                "Error processing action {} for formulas: {}", orm_action.id, exc
            )
            errors.append(
                f"Error processing action on element '{action_create.element}': {exc}"
            )
        finally:
            if pushed:
                context.pop_current_record_context()

    return errors


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
        context = page_formula_context(page)
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

    for entries in by_item.values():
        first = entries[0]
        formulas = {entry["field"]: entry["formula"] for entry in entries}
        tool_helpers.update_status(_repair_status(first))
        denied = False
        try:
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
