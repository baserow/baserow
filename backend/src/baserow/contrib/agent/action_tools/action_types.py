import json
import re
from typing import Any
from uuid import uuid4

from django.conf import settings

from baserow.contrib.agent.models import AgentAction
from baserow.contrib.integrations.core.constants import BODY_TYPE, HTTP_METHOD
from baserow.contrib.integrations.core.models import (
    CoreHTTPRequestService,
    CoreSMTPEmailService,
)
from baserow.core.formula.types import BASEROW_FORMULA_MODE_RAW, BaserowFormulaObject
from baserow.core.services.exceptions import (
    AddressNotAllowedDispatchException,
    RuntimeDispatchException,
)
from baserow.core.services.types import DispatchResult
from baserow.core.tools.errors import ToolInputError

from .registries import AgentActionDefaults, AgentActionType

HTTP_ACTION_MAX_BODY_BYTES = 64 * 1024
"""The largest body a call may send, so a held call and its step stay readable."""

HTTP_ACTION_MAX_RESULT_CHARACTERS = 20_000
"""The longest response body the model reads, as text, before it is cut."""

HIDDEN_VALUE = "••••••••"
"""Shown in place of a value the builder fixed, where credentials usually sit."""

_HTTP_ROW_ERROR_KEY = re.compile(r"^(header|param|form_data)_\d+$")
_HTTP_ROW_FIELDS = {
    "header": "headers",
    "param": "query_params",
    "form_data": "form_data",
}


class SMTPEmailAgentActionType(AgentActionType):
    type = "smtp_email"

    def get_defaults(self) -> AgentActionDefaults:
        definitions = [
            ("to_email", "email", "The recipient's email address.", "to_emails"),
            ("subject", "string", "A concise subject for the email.", "subject"),
            (
                "body",
                "string",
                "The complete plain-text email message, ready to send as it is. "
                "Sign it with what you know and never leave a placeholder such as "
                "[Your Name].",
                "body",
            ),
        ]
        inputs, service = (
            [],
            {
                "use_instance_smtp_settings": (
                    self.service_type.instance_smtp_unavailable_reason() is None
                ),
                "body_type": "plain",
            },
        )
        for name, input_type, description, field in definitions:
            input_id = str(uuid4())
            inputs.append(
                {
                    "id": input_id,
                    "name": name,
                    "type": input_type,
                    "description": description,
                    "required": True,
                }
            )
            service[field] = BaserowFormulaObject.create(
                f"get('tool_input.{input_id}')", mode="simple"
            )
        return {
            "name": "send_email",
            "description": "Send an email when the user asks to contact someone "
            "or deliver information by email. The recipient receives exactly what "
            "you provide.",
            "inputs": inputs,
            "service": service,
        }

    def get_preview_values(
        self, service: CoreSMTPEmailService, resolved_values: dict[str, Any]
    ) -> dict[str, Any]:
        sender = (
            {"from_email": settings.FROM_EMAIL, "from_name": ""}
            if service.use_instance_smtp_settings
            else {key: resolved_values[key] for key in ("from_email", "from_name")}
        )
        content = ("to_emails", "cc_emails", "bcc_emails", "subject", "body")
        return {
            **sender,
            **{key: resolved_values[key] for key in content},
            "body_type": service.body_type,
        }


class HTTPRequestAgentActionType(AgentActionType):
    type = "http_request"

    def get_defaults(self) -> AgentActionDefaults:
        body_id = str(uuid4())
        return {
            "name": "call_api",
            "description": "Send a request to the API when the user asks to look "
            "something up in it or to change something there. Describe what the "
            "API answered.",
            "inputs": [
                {
                    "id": body_id,
                    "name": "body",
                    "type": "string",
                    "description": "Only the JSON body of the request, for "
                    'example {"name": "Ada"}. The method, address and headers '
                    "are already set.",
                    "required": True,
                }
            ],
            # The URL is left for the builder: until it is set the action is
            # not ready and isn't offered.
            "service": {
                "http_method": HTTP_METHOD.POST,
                "body_type": BODY_TYPE.JSON,
                "body_content": BaserowFormulaObject.create(
                    f"get('tool_input.{body_id}')", mode="simple"
                ),
            },
        }

    def get_configuration_errors(self, action: AgentAction) -> dict[str, str]:
        # A header, query parameter or form data row is reported by the list it
        # sits in, which is what the action's form labels.
        errors = {}
        for key, error in super().get_configuration_errors(action).items():
            match = _HTTP_ROW_ERROR_KEY.match(key)
            errors[_HTTP_ROW_FIELDS[match.group(1)] if match else key] = error
        return errors

    def prepare(self, action: AgentAction, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Resolve a call, and refuse one whose body can't be sent as it is, so it
        neither waits for approval nor goes out.

        :raises ToolInputError: When a JSON body isn't valid JSON, or the body is
            larger than ``HTTP_ACTION_MAX_BODY_BYTES``.
        """

        resolved_values = super().prepare(action, arguments)
        service = action.service.specific
        if service.body_type == BODY_TYPE.FORM:
            body = "".join(
                resolved_values[f"form_data_{row.id}"]
                for row in service.form_data.all()
            )
        elif service.body_type in (BODY_TYPE.JSON, BODY_TYPE.RAW):
            body = resolved_values["body_content"]
        else:
            body = ""
        if len(body.encode()) > HTTP_ACTION_MAX_BODY_BYTES:
            raise ToolInputError(
                f"The request body is larger than {HTTP_ACTION_MAX_BODY_BYTES // 1024}"
                " KB."
            )
        if service.body_type == BODY_TYPE.JSON and body:
            try:
                json.loads(body, strict=False)
            except json.JSONDecodeError as exc:
                raise ToolInputError(
                    f"The request body is not valid JSON: {exc.msg}.",
                    hint="Send the body as one JSON value, with every string "
                    "quoted and escaped.",
                ) from exc
        return resolved_values

    def get_preview_values(
        self, service: CoreHTTPRequestService, resolved_values: dict[str, Any]
    ) -> dict[str, Any]:
        def rows(items, prefix):
            # What the model chose is shown. What the builder fixed is where an
            # API key or a token sits, so it stays hidden.
            return {
                row.key: (
                    resolved_values[f"{prefix}_{row.id}"]
                    if _reads_tool_input(row.value)
                    else HIDDEN_VALUE
                )
                for row in items
            }

        values = {
            "http_method": service.http_method,
            "url": resolved_values["url"],
            "query_params": rows(service.query_params.all(), "param"),
            "headers": rows(service.headers.all(), "header"),
            "body_type": service.body_type,
        }
        if service.body_type == BODY_TYPE.FORM:
            values["form_data"] = rows(service.form_data.all(), "form_data")
        elif service.body_type != BODY_TYPE.NONE:
            values["body_content"] = resolved_values["body_content"]
        # A request without any of a kind of row reads better without its name.
        return {key: value for key, value in values.items() if value != {}}

    def dispatch(
        self, action: AgentAction, resolved_values: dict[str, Any]
    ) -> DispatchResult:
        """
        Send the request. A refused or unreachable address is an error the
        model can act on, rather than an unknown failure.
        """

        try:
            return super().dispatch(action, resolved_values)
        except AddressNotAllowedDispatchException as exc:
            raise ToolInputError(
                "This address can't be called from this Baserow instance."
            ) from exc
        except RuntimeDispatchException as exc:
            raise ToolInputError(
                "The request didn't reach the server or got no complete answer.",
                hint="Say that the API couldn't be reached. Try again only if "
                "the user asks to.",
            ) from exc

    def get_tool_result(self, action: AgentAction, result: DispatchResult) -> Any:
        """
        :return: The status, content type and body of the response. A body longer
            than ``HTTP_ACTION_MAX_RESULT_CHARACTERS`` comes back as the start
            of its text, as the model reads it in every later turn.
        """

        data = result.data
        body = data["body"]
        text = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
        answer = {
            "status_code": data["status_code"],
            "content_type": data["headers"].get("content-type", ""),
            "body": body,
            "body_omitted": data["body_omitted"],
        }
        if len(text) > HTTP_ACTION_MAX_RESULT_CHARACTERS:
            answer["body"] = text[:HTTP_ACTION_MAX_RESULT_CHARACTERS]
            answer["body_truncated"] = True
        return answer


def _reads_tool_input(value: dict[str, Any]) -> bool:
    """
    :param value: A stored formula.
    :return: Whether it is built from what the model provides.
    """

    return value.get("mode") != BASEROW_FORMULA_MODE_RAW and "tool_input." in (
        value.get("formula") or ""
    )
