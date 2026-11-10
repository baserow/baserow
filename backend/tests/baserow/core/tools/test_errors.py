from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError

import pytest
from pydantic import ValidationError
from rest_framework.exceptions import APIException
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.api.exceptions import RequestBodyValidationException
from baserow.core.exceptions import (
    InstanceTypeDoesNotExist,
    PermissionDenied,
    UserNotInWorkspace,
    WorkspaceDoesNotExist,
    WorkspaceUserIsLastAdmin,
)
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.tools.errors import (
    INTERNAL_ERROR_MESSAGE,
    NOT_FOUND_MESSAGE,
    PERMISSION_DENIED_MESSAGE,
    ToolError,
    ToolErrorCode,
    ToolInputError,
    classify_item_error,
    classify_tool_error,
    finish_batch,
    item_error,
    item_error_message,
)


class PaymentRequired(APIException):
    status_code = 402


@pytest.mark.parametrize(
    "error,expected",
    [
        (ToolInputError("Pick a table."), ("invalid_input", "Pick a table.")),
        (ObjectDoesNotExist("private"), ("not_found", NOT_FOUND_MESSAGE)),
        (WorkspaceDoesNotExist("private"), ("not_found", NOT_FOUND_MESSAGE)),
        (UserNotInWorkspace(), ("not_found", NOT_FOUND_MESSAGE)),
        (PermissionDenied(), ("permission_denied", PERMISSION_DENIED_MESSAGE)),
        (DRFPermissionDenied("Deactivated."), ("permission_denied", "Deactivated.")),
        (DjangoValidationError("Bad."), ("invalid_input", "Invalid value. Bad.")),
        (
            DRFValidationError({"name": "Bad."}),
            ("invalid_input", "Invalid value. name: Bad."),
        ),
        (
            RequestBodyValidationException({"name": "Bad."}),
            ("invalid_input", "Invalid value. name: Bad."),
        ),
        (PaymentRequired("Needs a licence."), ("failed", "Needs a licence.")),
        (
            ServiceImproperlyConfiguredDispatchException("No field."),
            ("invalid_input", "Invalid value. No field."),
        ),
        (
            InstanceTypeDoesNotExist("bad", "unknown"),
            ("invalid_input", "'bad' is not a valid type."),
        ),
        (InstanceTypeDoesNotExist("model not registered"), ("failed", None)),
        (RuntimeError("Not found in this workspace."), ("failed", None)),
        (APIException("private"), ("failed", None)),
        (
            ValidationError.from_exception_data(
                "Model", [{"type": "int_parsing", "loc": ("id",), "input": "x"}]
            ),
            ("failed", None),
        ),
        (
            type("RelatedObjectDoesNotExist", (ObjectDoesNotExist, AttributeError), {})(
                "private"
            ),
            ("failed", None),
        ),
    ],
)
def test_tool_errors_get_one_code_and_message(error, expected):
    code, message = expected
    assert classify_tool_error(error) == ToolError(ToolErrorCode(code), message)


class _Conflict(Exception):
    pass


def test_tool_error_serializes_its_hint_only_when_set():
    assert ToolError(ToolErrorCode.NOT_FOUND, "Gone.").to_dict() == {
        "code": "not_found",
        "message": "Gone.",
    }
    assert ToolError(ToolErrorCode.FAILED, None, "Retry later.").to_dict() == {
        "code": "failed",
        "message": INTERNAL_ERROR_MESSAGE,
        "hint": "Retry later.",
    }


def test_input_errors_keep_the_hint_apart_from_the_message():
    error = classify_tool_error(ToolInputError("Field 3 is not here.", "IDs: [1]"))

    assert error == ToolError(
        ToolErrorCode.INVALID_INPUT, "Field 3 is not here.", "IDs: [1]"
    )


def test_item_errors_name_the_item_and_keep_tool_details():
    error = ToolError(ToolErrorCode.INVALID_FORMULA, "Unknown function.")

    assert item_error("Total", error, formula="sum(") == {
        "item": "Total",
        "code": "invalid_formula",
        "message": "Unknown function.",
        "formula": "sum(",
    }


def test_item_errors_are_classified_with_tool_conflicts():
    assert classify_item_error(_Conflict("Name used."), (_Conflict,)) == ToolError(
        ToolErrorCode.CONFLICT, "Name used."
    )
    assert classify_item_error(ObjectDoesNotExist("x")).code == "not_found"
    assert classify_item_error(WorkspaceUserIsLastAdmin("Not empty.")) == ToolError(
        ToolErrorCode.INVALID_INPUT, "Not empty."
    )


@pytest.mark.parametrize(
    "error",
    [
        KeyError("private"),
        ValueError("invalid literal for int() with base 10: 'abc'"),
        TypeError("private"),
        ValidationError.from_exception_data(
            "Model", [{"type": "int_parsing", "loc": ("id",), "input": "x"}]
        ),
        InstanceTypeDoesNotExist("model not registered"),
    ],
    ids=["key", "value", "type", "pydantic", "unregistered-model"],
)
def test_unexpected_item_errors_are_logged_and_get_no_message(error, mocker):
    log = mocker.patch("baserow.core.tools.errors.logger.exception")

    assert classify_item_error(error) == ToolError(ToolErrorCode.FAILED, None)
    assert item_error_message(error) == INTERNAL_ERROR_MESSAGE
    assert log.call_count == 2


def test_baserow_item_errors_without_a_message_name_their_class():
    assert classify_item_error(WorkspaceUserIsLastAdmin()) == ToolError(
        ToolErrorCode.INVALID_INPUT, "WorkspaceUserIsLastAdmin"
    )


def test_a_batch_that_changed_nothing_because_items_failed_has_an_error():
    one = item_error("A", ToolError(ToolErrorCode.CONFLICT, "A exists."))
    two = item_error("B", ToolError(ToolErrorCode.INVALID_INPUT, "B is bad."))

    single = finish_batch({"created": []}, False, [one], "Nothing was created.")
    several = finish_batch({"created": []}, False, [one, two], "Nothing was created.")

    assert single["error"] == {"code": "conflict", "message": "A exists."}
    assert several["error"] == {"code": "failed", "message": "Nothing was created."}
    assert several["errors"] == [one, two] and several["changed"] is False


def test_a_batch_without_failures_or_with_changes_has_no_error():
    one = item_error("A", ToolError(ToolErrorCode.CONFLICT, "A exists."))
    stale = {"created": [1], "error": {"code": "failed"}, "errors": [one]}

    assert finish_batch(stale, True, [one], "x") == {
        "created": [1],
        "errors": [one],
        "changed": True,
    }
    assert finish_batch({"created": []}, False, [], "x") == {
        "created": [],
        "changed": False,
    }
