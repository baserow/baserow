"""
Application builder workflow action tools shared by the clients that act for a
user.
"""

from typing import Annotated, Any

from django.db import transaction
from django.utils.translation import gettext as _

from pydantic import Field

from baserow.contrib.builder.workflow_actions.handler import (
    BuilderWorkflowActionHandler,
)
from baserow.core.tools import ToolContext
from baserow.core.tools.errors import ToolInputError, raise_if_permission_denied

from . import BuilderWriteOptions, helpers
from .errors import client_item_error
from .formulas import (
    BuilderFormulaContext,
    apply_builder_formulas,
    check_formula_on_action,
    check_required_action_formulas,
)
from .pages import get_page_in_workspace
from .types import ActionCreate, ActionItem


def list_actions(
    ctx: ToolContext,
    page_id: Annotated[int, Field(description="The ID of the page, from list_pages.")],
) -> dict[str, Any]:
    """
    List the workflow actions of a page of an application builder: id, type, the
    element they belong to, the event that runs them (like click or submit) and
    their field mappings. Actions run when a visitor uses an element, like
    opening a page, showing a notification or changing rows.
    """

    page = get_page_in_workspace(ctx, page_id)
    ctx.update_status(_("Listing actions on %(name)s...") % {"name": page.name})

    actions = helpers.list_workflow_actions(ctx.user, page)
    return {"workflow_actions": [a.model_dump() for a in actions]}


def create_actions_with_options(
    ctx: ToolContext,
    page_id: int,
    actions: list[ActionCreate],
    options: BuilderWriteOptions,
) -> dict[str, Any]:
    """``create_actions`` with what a client adds to it."""

    page = get_page_in_workspace(ctx, page_id)
    integration = helpers.get_local_baserow_integration(ctx.user, page.builder)

    refs = dict(options.known_refs)
    data_source_refs = dict(options.known_data_source_refs)
    contexts: dict[int, BuilderFormulaContext] = {}
    created: list[dict] = []
    pairs: list[tuple[Any, ActionCreate]] = []
    errors: list[str] = []
    with transaction.atomic():
        for action_create in actions:
            ctx.update_status(
                _("Creating %(type)s action...") % {"type": action_create.type}
            )
            try:
                # The check needs the element the action landed on, and failing it
                # takes the action back out.
                with transaction.atomic():
                    action, action_id = helpers.create_workflow_action(
                        ctx.user,
                        page,
                        action_create,
                        refs,
                        data_source_refs,
                        integration,
                    )
                    if not options.defer_required_formulas:
                        check_required_action_formulas(
                            contexts, page, action, action_create
                        )
            except Exception as exc:
                raise_if_permission_denied(exc)
                errors.append(
                    f"{action_create.type} on {action_create.element}: "
                    f"{options.item_error(exc)}"
                )
                continue
            pairs.append((action, action_create))
            created.append(
                {
                    "id": action_id,
                    "type": action_create.type,
                    "element": action_create.element,
                    "event": action_create.event,
                }
            )

    formula_errors = apply_builder_formulas(ctx, page, pairs, "action")

    result: dict[str, Any] = {"created_actions": created}
    if formula_errors:
        result["formula_errors"] = formula_errors
    if errors:
        result["errors"] = errors
    return result


def create_actions(
    ctx: ToolContext,
    page_id: Annotated[int, Field(description="The ID of the page, from list_pages.")],
    actions: Annotated[
        list[ActionCreate], Field(description="The workflow actions to create.")
    ],
) -> dict[str, Any]:
    """
    Create workflow actions on elements of a page, by element ID from list_elements:
    show a notification, open a page of this application, create, update or delete a
    row, refresh a data source, or log out. Use event "click" for a button or link,
    "submit" for a form_container, "after_login" for an auth_form. For a table button
    column use "<column name>_click" or "<uid>_click", with the column's uid from
    list_elements. A ref only works inside the call that creates it, so here use IDs.

    Give dynamic values as formulas in Baserow formula syntax, like
    get('form_data.<element id>') or, on a table button, get('current_record.id').
    get('previous_action.<action id>.<field>') reads what an earlier action returned.
    Plain text in a title, description or parameter is stored as fixed text.
    Descriptions are not turned into formulas: a value that isn't a valid formula is
    left empty and listed in formula_errors. A field value can then be set with
    add_action_field_mapping. A row action can't run without its row_id, so one that
    isn't a valid formula or number is listed in errors and that action isn't created.
    """

    return create_actions_with_options(
        ctx, page_id, actions, BuilderWriteOptions(item_error=client_item_error)
    )


def add_action_field_mapping(
    ctx: ToolContext,
    action_id: Annotated[
        int, Field(description="The ID of the action, from list_actions.")
    ],
    field_id: Annotated[
        int, Field(description="The ID of a field of the table the action writes to.")
    ],
    value_formula: Annotated[
        str,
        Field(
            description=(
                "The value, as a formula, like get('form_data.<element id>'). "
                "Quote fixed text: 'like this'."
            )
        ),
    ],
) -> dict[str, Any]:
    """
    Set the value a create_row or update_row action writes to one field, replacing
    the value that field has. The action's other fields stay as they are. A value that
    isn't a valid formula is refused and nothing changes.
    """

    action = helpers.get_writable_action(ctx.user, ctx.workspace, action_id)
    ctx.update_status(_("Adding field mapping to action %(id)d...") % {"id": action_id})

    problem = check_formula_on_action(
        action.page, action, "value_formula", value_formula
    )
    if problem:
        raise ToolInputError(problem)

    helpers.add_field_mapping_to_action(
        ctx.user, ctx.workspace, action_id, field_id, value_formula
    )
    updated = BuilderWorkflowActionHandler().get_workflow_action(action_id)
    return {"updated_action": ActionItem.from_orm(updated).model_dump()}
