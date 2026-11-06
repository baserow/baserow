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
)
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.tools.errors import (
    NOT_FOUND_MESSAGE,
    PERMISSION_DENIED_MESSAGE,
    ToolError,
    ToolErrorCode,
    ToolInputError,
    classify_tool_error,
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
