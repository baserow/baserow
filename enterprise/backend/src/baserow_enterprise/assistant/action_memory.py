"""Keep a bounded memory of verified tool actions."""

import json
from collections.abc import Iterator
from dataclasses import dataclass, replace
from hashlib import sha256
from typing import Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

MAX_VERIFIED_TOOL_OUTCOMES = 12
MAX_VERIFIED_TOOL_OUTCOMES_CHARS = 4000

_MEMORY_METADATA_KEY = "baserow_assistant_memory"
_MEMORY_VERSION = 1
_MAX_VALUE_DEPTH = 8
_MAX_VALUE_ITEMS = 12
_MAX_VALUE_CHARS = 160
_MAX_TOOL_NAME_CHARS = 96
_MUTATION_PREFIXES = (
    "create_",
    "update_",
    "delete_",
    "add_",
    "setup_",
    "set_",
    "move_",
)
_MUTATION_RESULT_PREFIXES = (
    "created_",
    "updated_",
    "deleted_",
    "added_",
    "moved_",
)
_TOP_LEVEL_ERROR_RESULT_PREFIXES = (
    "created_",
    "updated_",
    "deleted_",
    "added_",
    "reused_",
    "setup_",
)
_REPORTED_ERROR_RESULT_PREFIXES = (
    *_MUTATION_RESULT_PREFIXES,
    "reused_",
    "setup_",
)
_RESULT_ERROR_KEYS = ("errors", "field_errors", "formula_errors", "notes")


@dataclass(frozen=True)
class _ToolExecution:
    tool_name: str
    arguments: dict[str, Any]
    result: Any
    outcome: str


@dataclass(frozen=True)
class MutationEvidence:
    """A mutating tool result that can ground a completion claim."""

    tool_name: str
    arguments: dict[str, Any]
    result: Any
    changed: bool
    completed: bool


_PendingCalls = dict[str, tuple[str, dict[str, Any]]]


def _has_user_prompt(message: ModelMessage) -> bool:
    return isinstance(message, ModelRequest) and any(
        isinstance(part, UserPromptPart) for part in message.parts
    )


def _tool_arguments(part: ToolCallPart) -> dict[str, Any] | None:
    try:
        return part.args_as_dict()
    except Exception:
        return None


def _is_mutating_call(tool_name: str, arguments: dict[str, Any]) -> bool:
    if tool_name.startswith(_MUTATION_PREFIXES):
        return True
    return tool_name == "generate_formula" and arguments.get("save_to_field") is True


def _remember_mutating_calls(
    message: ModelResponse, pending_calls: _PendingCalls
) -> None:
    for part in message.parts:
        if not isinstance(part, ToolCallPart):
            continue
        arguments = _tool_arguments(part)
        if arguments is not None and _is_mutating_call(part.tool_name, arguments):
            pending_calls[part.tool_call_id] = (part.tool_name, arguments)


def _returned_executions(
    message: ModelRequest, pending_calls: _PendingCalls
) -> Iterator[_ToolExecution]:
    for part in message.parts:
        if not isinstance(part, ToolReturnPart):
            continue
        pending_call = pending_calls.pop(part.tool_call_id, None)
        if pending_call is None:
            continue
        tool_name, arguments = pending_call
        yield _ToolExecution(
            tool_name=tool_name,
            arguments=arguments,
            result=part.content,
            outcome=part.outcome,
        )


def _tool_executions(
    messages: list[ModelMessage], *, reset_between_turns: bool = False
) -> Iterator[_ToolExecution]:
    pending_calls: _PendingCalls = {}

    for message in messages:
        if reset_between_turns and _has_user_prompt(message):
            pending_calls.clear()

        if isinstance(message, ModelResponse):
            _remember_mutating_calls(message, pending_calls)
        elif isinstance(message, ModelRequest):
            yield from _returned_executions(message, pending_calls)


def _compact_value(value: Any, depth: int = 0) -> Any:
    if depth >= _MAX_VALUE_DEPTH:
        return "..."

    if isinstance(value, dict):
        items = list(value.items())[:_MAX_VALUE_ITEMS]
        compacted = {
            str(key): _compact_value(item, depth + 1)
            for key, item in items
            if key != "thought"
        }
        if len(value) > _MAX_VALUE_ITEMS:
            compacted["_truncated"] = len(value) - _MAX_VALUE_ITEMS
        return compacted

    if isinstance(value, (list, tuple)):
        compacted = [
            _compact_value(item, depth + 1) for item in value[:_MAX_VALUE_ITEMS]
        ]
        if len(value) > _MAX_VALUE_ITEMS:
            compacted.append({"_truncated": len(value) - _MAX_VALUE_ITEMS})
        return compacted

    if isinstance(value, str):
        if len(value) <= _MAX_VALUE_CHARS:
            return value
        return value[: _MAX_VALUE_CHARS - 3] + "..."

    if value is None or isinstance(value, (bool, int, float)):
        return value

    return str(value)[:_MAX_VALUE_CHARS]


def _has_result_with_prefix(result: dict[str, Any], prefixes: tuple[str, ...]) -> bool:
    return any(
        key.startswith(prefixes) and bool(value) for key, value in result.items()
    )


def _has_reported_errors(result: dict[str, Any]) -> bool:
    return any(result.get(key) for key in _RESULT_ERROR_KEYS)


def _has_nested_value(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_has_nested_value(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_has_nested_value(item) for item in value)
    return bool(value)


def _mutation_value_changed(key: str, value: Any) -> bool:
    if key == "created_view_filters":
        return (
            any(
                _has_nested_value(item.get("filters"))
                for item in value
                if isinstance(item, dict)
            )
            if isinstance(value, list)
            else False
        )
    return _has_nested_value(value)


def _is_failed_result(result: Any, outcome: str) -> bool:
    if outcome != "success":
        return True
    if not isinstance(result, dict):
        return False
    if result.get("status") in ("error", "warning"):
        return True
    if result.get("error") and not _has_result_with_prefix(
        result, _TOP_LEVEL_ERROR_RESULT_PREFIXES
    ):
        return True
    return _has_reported_errors(result) and not _has_result_with_prefix(
        result, _REPORTED_ERROR_RESULT_PREFIXES
    )


def _execution_changed_data(execution: _ToolExecution) -> bool:
    result = execution.result
    if _is_failed_result(result, execution.outcome):
        return False
    if not isinstance(result, dict):
        return result not in (None, "")
    if result.get("changed") is False:
        return False

    mutation_values = [
        (key, value)
        for key, value in result.items()
        if key.startswith(_MUTATION_RESULT_PREFIXES)
    ]
    if mutation_values:
        return any(
            _mutation_value_changed(key, value) for key, value in mutation_values
        )
    if execution.tool_name.startswith("create_"):
        return False
    if _has_reported_errors(result):
        return False
    return bool(result)


def _execution_completed_change(execution: _ToolExecution) -> bool:
    result = execution.result
    if execution.outcome != "success":
        return False
    if isinstance(result, dict) and (
        result.get("status") in {"error", "warning"}
        or result.get("error")
        or _has_reported_errors(result)
    ):
        return False
    return _execution_changed_data(execution)


def _mutation_evidence(execution: _ToolExecution) -> MutationEvidence:
    return MutationEvidence(
        tool_name=execution.tool_name,
        arguments=execution.arguments,
        result=execution.result,
        changed=_execution_changed_data(execution),
        completed=_execution_completed_change(execution),
    )


def get_mutation_evidence(messages: list[ModelMessage]) -> list[MutationEvidence]:
    """
    Return the mutation results present in model history.

    :param messages: The model message history to inspect.
    :return: Evidence from stored outcomes followed by live tool executions.
    """

    stored = []
    for outcome in get_verified_tool_outcomes(messages):
        execution = _ToolExecution(
            tool_name=outcome.get("tool", ""),
            arguments=outcome.get("arguments", {}),
            result=outcome.get("result"),
            outcome="success",
        )
        evidence = _mutation_evidence(execution)
        stored.append(
            MutationEvidence(
                tool_name=evidence.tool_name,
                arguments=evidence.arguments,
                result=evidence.result,
                changed=_stored_flag(outcome, "changed", evidence.changed),
                completed=_stored_flag(outcome, "completed", evidence.completed),
            )
        )
    return [*stored, *map(_mutation_evidence, _tool_executions(messages))]


def _stored_flag(outcome: dict[str, Any], key: str, fallback: bool) -> bool:
    value = outcome.get(key)
    return value if isinstance(value, bool) else fallback


def _request_fingerprint(tool_name: str | None, arguments: Any) -> str:
    request = json.dumps(
        [tool_name, arguments],
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(request.encode()).hexdigest()


def _verified_outcome(execution: _ToolExecution) -> dict[str, Any]:
    arguments = dict(execution.arguments)
    arguments.pop("thought", None)
    evidence = _mutation_evidence(execution)
    return {
        "tool": execution.tool_name,
        "arguments": _compact_value(arguments),
        "result": _compact_value(execution.result),
        "changed": evidence.changed,
        "completed": evidence.completed,
        "failed": _is_failed_result(execution.result, execution.outcome),
        "_request_fingerprint": _request_fingerprint(execution.tool_name, arguments),
    }


def _verified_outcomes(messages: list[ModelMessage]) -> list[dict[str, Any]]:
    return [
        _verified_outcome(execution)
        for execution in _tool_executions(messages, reset_between_turns=True)
    ]


def _stored_outcomes(message: ModelMessage) -> list[dict[str, Any]] | None:
    metadata = getattr(message, "metadata", None)
    if not isinstance(metadata, dict):
        return None
    memory = metadata.get(_MEMORY_METADATA_KEY)
    if not isinstance(memory, dict) or memory.get("version") != _MEMORY_VERSION:
        return None
    outcomes = memory.get("verified_tool_outcomes")
    if not isinstance(outcomes, list):
        return None
    return [outcome for outcome in outcomes if isinstance(outcome, dict)]


def get_verified_tool_outcomes(
    messages: list[ModelMessage],
) -> list[dict[str, Any]]:
    """
    Return verified tool outcomes stored in history metadata.

    :param messages: The model message history to inspect.
    :return: The outcomes of the most recent message carrying memory metadata.
    """

    for message in reversed(messages):
        outcomes = _stored_outcomes(message)
        if outcomes is not None:
            return outcomes
    return []


def _outcome_fingerprint(outcome: dict[str, Any]) -> str:
    existing = outcome.get("_request_fingerprint")
    if isinstance(existing, str):
        return existing
    return _request_fingerprint(
        outcome.get("tool"),
        outcome.get("arguments"),
    )


def _serialized_length(outcomes: list[dict[str, Any]]) -> int:
    return len(json.dumps(outcomes, separators=(",", ":"), default=str))


def _truncated_outcome(outcome: dict[str, Any]) -> dict[str, Any]:
    """Keep only the tool name and outcome flags of an oversized outcome."""

    return {
        "tool": str(outcome.get("tool", ""))[:_MAX_TOOL_NAME_CHARS],
        "changed": _outcome_changed(outcome),
        "completed": _outcome_completed(outcome),
        "failed": _outcome_failed(outcome),
        "_truncated": True,
        "_request_fingerprint": _outcome_fingerprint(outcome),
    }


def _merge_outcomes(
    previous: list[dict[str, Any]], new: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for outcome in [*previous, *new]:
        fingerprint = _outcome_fingerprint(outcome)
        existing = merged.get(fingerprint)
        if existing and _outcome_changed(existing) and _is_reused_only(outcome):
            merged.pop(fingerprint)
            merged[fingerprint] = existing
            continue
        merged.pop(fingerprint, None)
        merged[fingerprint] = outcome

    bounded = list(merged.values())[-MAX_VERIFIED_TOOL_OUTCOMES:]
    while (
        len(bounded) > 1
        and _serialized_length(bounded) > MAX_VERIFIED_TOOL_OUTCOMES_CHARS
    ):
        bounded.pop(0)
    if bounded and _serialized_length(bounded) > MAX_VERIFIED_TOOL_OUTCOMES_CHARS:
        bounded[0] = _truncated_outcome(bounded[0])
    return bounded


def _outcome_changed(outcome: dict[str, Any]) -> bool:
    evidence = _outcome_evidence(outcome)
    return _stored_flag(outcome, "changed", evidence.changed)


def _outcome_completed(outcome: dict[str, Any]) -> bool:
    evidence = _outcome_evidence(outcome)
    return _stored_flag(outcome, "completed", evidence.completed)


def _outcome_failed(outcome: dict[str, Any]) -> bool:
    failed = outcome.get("failed")
    if isinstance(failed, bool):
        return failed
    return _is_failed_result(outcome.get("result"), "success")


def _is_reused_only(outcome: dict[str, Any]) -> bool:
    result = outcome.get("result")
    if not isinstance(result, dict):
        return False
    reused = any(key.startswith("reused_") and value for key, value in result.items())
    changed = any(
        key.startswith(_MUTATION_RESULT_PREFIXES)
        and _mutation_value_changed(key, value)
        for key, value in result.items()
    )
    return bool(reused and not changed and not _outcome_failed(outcome))


def _outcome_evidence(outcome: dict[str, Any]) -> MutationEvidence:
    return _mutation_evidence(
        _ToolExecution(
            tool_name=outcome.get("tool", ""),
            arguments=outcome.get("arguments", {}),
            result=outcome.get("result"),
            outcome="success",
        )
    )


def _last_response_index(messages: list[ModelMessage]) -> int | None:
    return next(
        (
            index
            for index in range(len(messages) - 1, -1, -1)
            if isinstance(messages[index], ModelResponse)
        ),
        None,
    )


def _attach_outcomes(
    messages: list[ModelMessage], outcomes: list[dict[str, Any]]
) -> list[ModelMessage]:
    if not outcomes:
        return messages
    response_index = _last_response_index(messages)
    if response_index is None:
        return messages

    response = messages[response_index]
    metadata = dict(response.metadata or {})
    metadata[_MEMORY_METADATA_KEY] = {
        "version": _MEMORY_VERSION,
        "verified_tool_outcomes": outcomes,
    }
    messages[response_index] = replace(response, metadata=metadata)
    return messages


def carry_verified_actions(
    source_history: list[ModelMessage], compacted_history: list[ModelMessage]
) -> list[ModelMessage]:
    """
    Carry verified actions into compacted history metadata.

    :param source_history: The full history to harvest outcomes from.
    :param compacted_history: The compacted history to attach outcomes to.
    :return: The compacted history with merged outcomes attached.
    """

    stored_outcomes = get_verified_tool_outcomes(source_history)
    new_outcomes = _verified_outcomes(source_history)
    outcomes = _merge_outcomes(stored_outcomes, new_outcomes)
    return _attach_outcomes(compacted_history, outcomes)
