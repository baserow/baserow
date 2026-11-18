"""
Sub-agents for the automation assistant tools.

Contains:
- ``AssistantFormulaContext``: Automation-specific formula context.
- ``get_generate_formulas_tool()``: Gets the automation formula generator.
- ``repair_formula_errors()``: Generates the formulas the shared tools could not
  store, after their transaction.
"""

import re
from typing import TYPE_CHECKING, Any, Callable, NamedTuple

from django.db import transaction
from django.utils.translation import gettext as _

from loguru import logger

from baserow.contrib.automation.nodes.exceptions import AutomationNodeDoesNotExist
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.tools import nodes as shared_nodes
from baserow.contrib.automation.tools.formulas import formula_error
from baserow.contrib.automation.tools.types import (
    SERVICE_ATTRIBUTES,
    matching_branches,
)
from baserow.core.formula.literals import FORMULA_PREFIX
from baserow.core.services.models import Service
from baserow.core.tools import ToolContext
from baserow.core.tools.formula_utils import (
    BaseFormulaContext,
    create_example_from_json_schema,
    formula_desc,
    minimize_json_schema,
)
from baserow_enterprise.assistant.tools.shared import raise_if_permission_denied
from baserow_enterprise.assistant.tools.shared.agents import get_formula_generator

from .prompts import GENERATE_FORMULA_PROMPT
from .types.node import AutomationFieldValue, NodeUpdate, RouterEdgeUpdate

if TYPE_CHECKING:
    from baserow_enterprise.assistant.deps import ToolHelpers
    from baserow_enterprise.assistant.model_profiles import (
        ResolvedAssistantModelProfile,
    )


class AssistantFormulaContext(BaseFormulaContext):
    """
    Automation-specific formula context.

    Wraps node data in the ``{"previous_node": {...}}`` structure expected
    by automation formula ``get()`` paths.
    """

    def add_node_context(
        self,
        node_id: int | str,
        node_context: dict[str, Any],
        context_metadata: dict[str, dict[str, str]] | None = None,
    ):
        """Add a node's output values to the formula context."""
        self.add_context(str(node_id), node_context, context_metadata)

    def get_formula_context(self) -> dict[str, Any]:
        """Return context wrapped in ``previous_node`` for automation formulas."""
        return {"previous_node": self.context}

    def __getitem__(self, key) -> Any:
        """Resolve paths like ``previous_node.1.0.field_name``."""
        return self._resolve_path(key, "previous_node")


def get_generate_formulas_tool(
    model_profile: "ResolvedAssistantModelProfile",
) -> Callable[[dict, BaseFormulaContext, int], dict[str, str]]:
    """Get the automation formula generator using the request model profile.

    :param model_profile: The model profile resolved for the assistant request.
    :return: A callable that generates automation formulas.
    """

    return get_formula_generator(GENERATE_FORMULA_PROMPT, model_profile)


# What each value is, for the generator, by the field a formula error names.
_DESCRIPTIONS = {
    "to_emails": "A comma separated list of email addresses to send the email to.",
    "cc_emails": "A comma separated list of email addresses to CC the email to.",
    "bcc_emails": "A comma separated list of email addresses to BCC the email to.",
    "subject": "The subject of the email.",
    "body": "The body content of the email.",
    "text": "The message content.",
    "prompt": "The AI prompt.",
    "row_id": "The ID of the row to act on.",
    "condition": "A boolean condition for the router branch.",
}


# Told for a value whose generated formula wasn't written because it changed
# meanwhile. Kept apart from formula_errors, which the model retries.
_KEPT_NOTE = (
    "Not updated: this value was changed, in the editor or by another client, "
    "while its formula was generated, so the newer value was kept. Tell the "
    "user, and don't change it unless they ask."
)

# A branch the label no longer names: the update refuses it and reports why.
_NO_BRANCH = object()


# The refusal of a row value whose field is not in the table.
_REFUSED_FIELD_RE = re.compile(r"Field (\d+) is not in table ")


def _current_values(service, errors: list[dict[str, Any]]) -> dict[Any, Any]:
    """
    What the values of a node's formula errors hold now, keyed as
    ``_request_key``. A row value is its mapping and whether it is enabled, or
    None when the field isn't mapped. A branch is found the way the update finds
    it.
    """

    mappings = (
        {
            mapping.field_id: (mapping.value, mapping.enabled)
            for mapping in service.field_mappings.all()
        }
        if any("field_id" in error for error in errors)
        else {}
    )
    edges = (
        list(service.edges.all())
        if any("edge_label" in error for error in errors)
        else []
    )
    values = {}
    for error in errors:
        if "field_id" in error:
            value = mappings.get(error["field_id"])
        elif "edge_label" in error:
            matches = matching_branches([e.label for e in edges], error["edge_label"])
            value = edges[matches[0]].condition if len(matches) == 1 else _NO_BRANCH
        else:
            # No default: a field stored under another name must fail here, not
            # read as empty.
            field = error["field"]
            value = getattr(service, SERVICE_ATTRIBUTES.get(field, field))
        values[_request_key(error)] = value
    return values


def _stored_values(node_id: int, errors: list[dict[str, Any]]) -> dict[Any, Any]:
    """
    The values of a node's formula errors as the tool left them, to tell after
    generation which ones changed meanwhile.

    :raises AutomationNodeDoesNotExist: When the node is gone, so nothing is
        generated for it.
    """

    node = AutomationNode.objects.filter(id=node_id).first()
    if node is None:
        raise AutomationNodeDoesNotExist(node_id)
    return _current_values(node.service.specific, errors)


def _request_key(error: dict[str, Any]) -> Any:
    """The key the generator answers a formula error under."""

    if "field_id" in error:
        return error["field_id"]
    if "edge_label" in error:
        return error["edge_label"]
    return error["field"]


def _describe(error: dict[str, Any], base: str) -> str:
    formula = error["formula"]
    description = f"{base} Value to resolve: {formula_desc(formula) if formula.strip() else 'not given'}"
    if formula.strip() and FORMULA_PREFIX not in formula.lower():
        description += f" It was written as an invalid formula: {error['error']}"
    return description


def formula_requests(
    node: AutomationNode,
    errors: list[dict[str, Any]],
    previous: AutomationNode | None = None,
) -> dict[Any, Any]:
    """
    What to ask the generator for a node's formula errors, keyed as
    ``_request_key``. A row value is described with its field.

    :param previous: The node ``node`` follows, so "the previous step" in a
        value's description is read as that node, not the trigger.
    """

    fields = {}
    if any("field_id" in error for error in errors):
        service = node.service.specific
        schema = service.get_type().generate_schema(service) or {}
        fields = {
            int(field["id"]): field
            for field in minimize_json_schema(schema).values()
            if "id" in field
        }

    follows = ""
    if previous is not None:
        label = f" ('{previous.label}')" if previous.label else ""
        follows = (
            f" This node follows node {previous.id}{label}: that node is the "
            "previous node or step."
        )

    requests: dict[Any, Any] = {}
    for error in errors:
        field = (
            fields.get(error["field_id"], {"desc": ""}) if "field_id" in error else None
        )
        base = field["desc"] if field else _DESCRIPTIONS.get(error["field"], "")
        description = _describe(error, base) + follows
        requests[_request_key(error)] = (
            {**field, "desc": description} if field else description
        )
    return requests


def _formula_update(
    node_id: int, errors: list[dict[str, Any]], generated: dict[Any, str]
) -> NodeUpdate:
    """The update that writes the generated formulas of a node's errors."""

    values: dict[str, Any] = {}
    for error in errors:
        formula = generated[_request_key(error)]
        if "field_id" in error:
            values.setdefault("values", []).append(
                AutomationFieldValue(field_id=error["field_id"], value=formula)
            )
        elif "edge_label" in error:
            values.setdefault("edges", []).append(
                RouterEdgeUpdate(label=error["edge_label"], condition=formula)
            )
        else:
            values[error["field"]] = formula
    return NodeUpdate(node_id=node_id, **values)


class WorkflowExamples:
    """
    The example data of a workflow's nodes for the generator, read once per
    workflow however many of its nodes are repaired.
    """

    def __init__(self, user, refs: dict[int, str] | None = None):
        self.user = user
        self.refs = refs or {}
        self._workflows: dict[int, tuple[dict, dict]] = {}

    def _read(self, workflow) -> tuple[dict, dict]:
        """
        The node each node of the workflow follows, by node ID, and the example
        data of the nodes that have any.
        """

        if workflow.id not in self._workflows:
            previous_of: dict[int, AutomationNode | None] = {}
            examples = {}
            for node, previous, _output in shared_nodes.nodes_in_order(
                self.user, workflow
            ):
                previous_of[node.id] = previous
                service = node.service.specific
                schema = service.get_type().generate_schema(service)
                if not schema:
                    continue
                metadata = minimize_json_schema(schema)
                metadata["node_id"] = node.id
                metadata["label"] = node.label
                metadata["node_type"] = node.get_type().type
                metadata["formula_path"] = shared_nodes.formula_path(node)
                if node.id in self.refs:
                    metadata["node_ref"] = self.refs[node.id]
                if previous is not None:
                    metadata["previous_node_id"] = previous.id
                examples[node.id] = (create_example_from_json_schema(schema), metadata)
            self._workflows[workflow.id] = (previous_of, examples)
        return self._workflows[workflow.id]

    def refs_of(self, workflow) -> dict[str, int]:
        """
        The ID of each node of the workflow by the ref it was created under. Refs
        repeat across workflows created in one call, so they are only read within
        one workflow.
        """

        previous_of, _examples = self._read(workflow)
        return {
            ref: node_id for node_id, ref in self.refs.items() if node_id in previous_of
        }

    def previous(self, node: AutomationNode) -> AutomationNode | None:
        """
        The node ``node`` follows, when the generator gets its data. One without
        example data, such as an iterator with no sample, isn't named.
        """

        previous_of, examples = self._read(node.workflow)
        previous = previous_of.get(node.id)
        return previous if previous is not None and previous.id in examples else None

    def context_for(self, node: AutomationNode) -> "AssistantFormulaContext":
        """
        The nodes that run before ``node`` on its path, the only ones its
        formulas can read.
        """

        previous_of, examples = self._read(node.workflow)
        context = AssistantFormulaContext()
        ancestor = previous_of.get(node.id)
        ancestors = []
        while ancestor is not None:
            ancestors.append(ancestor.id)
            ancestor = previous_of.get(ancestor.id)
        for node_id in reversed(ancestors):
            if node_id in examples:
                example, metadata = examples[node_id]
                context.add_node_context(node_id, example, metadata)
        return context


class RepairResult(NamedTuple):
    """What a repair left: the formula errors still to fix, and the values it
    kept because they changed while their formulas were generated."""

    formula_errors: list[dict[str, Any]]
    kept: list[dict[str, Any]]


def _failed_repair(
    raise_if_cancelled: Callable[[], None],
    exc: Exception,
    node_id: int,
    errors: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """The errors of a node whose repair failed. The nodes are committed, so a
    failed repair only leaves its errors."""

    raise_if_cancelled()
    raise_if_permission_denied(exc)
    logger.exception("Failed to repair formulas of node {}: {}", node_id, exc)
    return [{**error, "error": str(exc)} for error in errors]


def repair_formula_errors(
    tool_context: ToolContext,
    tool_helpers: "ToolHelpers",
    formula_errors: list[dict[str, Any]],
    refs: dict[int, str] | None = None,
) -> RepairResult:
    """
    Generate the formulas the shared tools could not store, and write each node's
    in its own transaction. Runs after the nodes are committed, so the model is
    never called inside a transaction. A value that changed while the formulas
    were generated is kept, not overwritten.

    :param formula_errors: All the errors of the call, so every value is read
        before any formula is generated.
    :param refs: The ref each node was created under, to help the generator.
    """

    if not formula_errors:
        return RepairResult([], [])

    generate_formula = get_generate_formulas_tool(tool_helpers.model_profile)
    raise_if_cancelled = tool_helpers.raise_if_cancelled
    field_ids = shared_nodes.table_field_ids()
    examples = WorkflowExamples(tool_context.user, refs)
    remaining: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []
    by_node: dict[int, list[dict[str, Any]]] = {}
    for error in formula_errors:
        by_node.setdefault(error["node_id"], []).append(error)

    # Read before any formula is generated: a value that differs when it is
    # written was changed meanwhile.
    stored: dict[int, dict[Any, Any]] = {}
    for node_id, node_errors in by_node.items():
        try:
            stored[node_id] = _stored_values(node_id, node_errors)
        except Exception as exc:
            remaining.extend(
                _failed_repair(raise_if_cancelled, exc, node_id, node_errors)
            )

    for node_id, node_stored in stored.items():
        node_errors = by_node[node_id]
        node_kept: list[dict[str, Any]] = []
        try:
            remaining.extend(
                _repair_node(
                    tool_context,
                    node_id,
                    node_errors,
                    raise_if_cancelled=raise_if_cancelled,
                    generate_formula=generate_formula,
                    field_ids=field_ids,
                    examples=examples,
                    stored=node_stored,
                    kept=node_kept,
                )
            )
        except Exception as exc:
            # A kept value stays kept: reported as an error, it would be retried
            # over the newer value.
            kept_keys = {_request_key(error) for error in node_kept}
            remaining.extend(
                _failed_repair(
                    raise_if_cancelled,
                    exc,
                    node_id,
                    [e for e in node_errors if _request_key(e) not in kept_keys],
                )
            )
        kept.extend(node_kept)
    return RepairResult(remaining, kept)


def kept_report(kept: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The kept values as the tools return them, each with what to do about it."""

    return [
        {
            **{
                key: error[key]
                for key in ("node_id", "node_label", "field", "field_id", "edge_label")
                if key in error
            },
            "note": _KEPT_NOTE,
        }
        for error in kept
    ]


def repaired_nodes(
    formula_errors: list[dict[str, Any]], remaining: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """The nodes a repair wrote a formula to: those with an error that is gone."""

    left = {(error["node_id"], _request_key(error)) for error in remaining}
    nodes = {
        error["node_id"]: error["node_label"]
        for error in formula_errors
        if (error["node_id"], _request_key(error)) not in left
    }
    return [{"node_id": node_id, "label": label} for node_id, label in nodes.items()]


def _refuses(message: str, error: dict[str, Any]) -> bool:
    """
    Whether an update refusal left the value of a formula error unset. A branch
    label or a field the update couldn't match only leaves that condition or
    field unset.
    """

    if "edge_label" in error:
        # A branch refusal starts with its label; the branches it lists after it
        # are not refused.
        return message.startswith(f"'{error['edge_label']}' ")
    field = _REFUSED_FIELD_RE.match(message)
    if field is None:
        return True
    return int(field.group(1)) == error.get("field_id")


def _repair_node(
    tool_context: ToolContext,
    node_id: int,
    node_errors: list[dict[str, Any]],
    *,
    raise_if_cancelled: Callable[[], None],
    generate_formula: Callable,
    field_ids: Callable[[int], set[int]],
    examples: WorkflowExamples,
    stored: dict[Any, Any],
    kept: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Generate one node's formulas and write them in their own transaction.

    :param raise_if_cancelled: Raises when the user cancelled the request.
    :param stored: The values of the node's errors before generation, keyed as
        ``_request_key``.
    :param kept: Gets the errors whose value changed meanwhile and was kept.
    :return: The node's formula errors that remain.
    """

    node = shared_nodes.get_node_in_workspace(tool_context, node_id)
    tool_context.update_status(
        _("Generating formulas for node '%(label)s'...") % {"label": node.label}
    )
    context = examples.context_for(node)
    requests = formula_requests(node, node_errors, examples.previous(node))
    generated = generate_formula(requests, context) or {}
    # The user may cancel while the model runs; nothing is written then.
    raise_if_cancelled()

    remaining = [e for e in node_errors if _request_key(e) not in generated]
    if len(remaining) == len(node_errors):
        return remaining
    repaired = []
    with transaction.atomic():
        # Locks the service row, so an editor save from now on waits for this
        # write and the values read below can't change before it.
        Service.objects.select_for_update(of=("self",)).filter(
            id=node.service_id
        ).exists()
        service = node.service.get_type().model_class.objects.get(id=node.service_id)
        now = _current_values(
            service, [e for e in node_errors if _request_key(e) in generated]
        )
        for key, value in now.items():
            error = next(e for e in node_errors if _request_key(e) == key)
            if value is _NO_BRANCH or value == stored[key]:
                repaired.append(error)
            else:
                kept.append(error)
        if not repaired:
            return remaining
        node, values, _changed = shared_nodes.update_node(
            tool_context,
            node.workflow,
            _formula_update(node_id, repaired, generated),
            field_ids,
            as_formulas=True,
            # The generator sees each node's ref and may name it by it.
            refs=examples.refs_of(node.workflow),
        )
    for error in repaired:
        refusals = [message for message in values.errors if _refuses(message, error)]
        if refusals:
            remaining.append({**error, "error": " ".join(refusals)})
    remaining.extend(
        formula_error(node, exc, **target) for exc, target in values.invalid
    )
    return remaining
