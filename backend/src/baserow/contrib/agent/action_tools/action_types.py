import json
import math
import re
from typing import Any
from urllib.parse import SplitResult, parse_qsl, quote_plus, urlsplit, urlunsplit
from uuid import uuid4

from django.conf import settings

from requests import exceptions as request_exceptions

from baserow.contrib.agent.models import AgentAction
from baserow.contrib.integrations.core.constants import BODY_TYPE, HTTP_METHOD
from baserow.contrib.integrations.core.models import (
    CoreHTTPRequestService,
    CoreSMTPEmailService,
)
from baserow.core.formula import resolve_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.formula.types import BASEROW_FORMULA_MODE_RAW, BaserowFormulaObject
from baserow.core.formula.validator import ensure_string
from baserow.core.services.exceptions import (
    AddressNotAllowedDispatchException,
    RedirectNotAllowedDispatchException,
    ResponseTooLargeDispatchException,
    RuntimeDispatchException,
)
from baserow.core.services.types import DispatchResult
from baserow.core.tools.errors import ToolFailedError, ToolInputError

from .data_providers import AgentActionDispatchContext
from .registries import AgentActionDefaults, AgentActionType

HTTP_ACTION_MAX_REQUEST_BYTES = 64 * 1024
"""The most a call may send: its URL, headers, query parameters and body."""

HTTP_ACTION_MAX_URL_BYTES = 8 * 1024
"""The longest URL a call may send, which servers commonly refuse past this."""

HTTP_ACTION_MAX_RESULT_CHARACTERS = 20_000
"""The longest response body the model reads, as text, before it is cut."""

HIDDEN_VALUE = "••••••••"
"""Shown in place of a value the approver doesn't read, where credentials sit."""

_HTTP_ROWS = (
    ("query_params", "param"),
    ("headers", "header"),
    ("form_data", "form_data"),
)
"""Each list of key and value rows, with the prefix of its resolved values."""

_SINGLE_INPUT = re.compile(r"""^get\(\s*(['"])tool_input\.([^'"]+)\1\s*\)$""")
_LINE_BREAK = re.compile(r"[\r\n]")


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
    """
    Sends a request to an API. The approver reads the values the model chose,
    and the URL. A value the builder fixed, or that mixes fixed text with an
    input, is where an API key usually sits: it isn't shown nor kept with a
    held call, and is resolved again once the call is approved.

    Resolved values are keyed by the position of each row, `headers.0` and so
    on, rather than by the row's ID. Rows are recreated when they're saved, so
    an edit undone while a call waits leaves the action unchanged with new IDs.
    """

    type = "http_request"

    def get_defaults(self) -> AgentActionDefaults:
        body_id = str(uuid4())
        return {
            "name": "call_api",
            "description": "Send a request to the API when the user asks to look "
            "something up in it or to change something there. Pass the whole JSON "
            "body as one string in `body`. Describe what the API answered.",
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
        # A row is reported by the list it sits in, which the form labels.
        service = action.service.specific
        lists = {
            f"{prefix}_{row.id}": field
            for field, prefix in _HTTP_ROWS
            for row in getattr(service, field).all()
        }
        errors = {
            lists.get(key, key): error
            for key, error in super().get_configuration_errors(action).items()
        }
        if (
            "url" not in errors
            and _reads_tool_input(service.url)
            and self._sends_fixed_values(service)
            and self._get_fixed_url(action, service) is None
        ):
            errors["url"] = "fixed_host"
        return errors

    def _sends_fixed_values(self, service: CoreHTTPRequestService) -> bool:
        """
        :return: Whether the request carries a value the approver doesn't read:
            one the builder typed, at least in part.
        """

        keys = ["url"]
        if service.body_type in (BODY_TYPE.JSON, BODY_TYPE.RAW):
            keys.append("body_content")
        for field, _ in _HTTP_ROWS:
            if field != "form_data" or service.body_type == BODY_TYPE.FORM:
                rows = getattr(service, field).all()
                keys.extend(f"{field}.{position}" for position in range(len(rows)))
        return any(
            (self._get_formula(service, key).get("formula") or "").strip()
            and not self._is_shown(service, key)
            for key in keys
        )

    def prepare(self, action: AgentAction, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Resolve a call, and refuse one that can't be sent as it is, so it
        neither waits for approval nor goes out.

        :raises ToolInputError: When the URL, a header or the body is malformed,
            the request is too large, or a request carrying hidden values would
            go to a host the agent chose.
        """

        service = action.service.specific
        resolved_values = super().prepare(action, arguments)
        values = {
            key: resolved_values[key]
            for key in ("url", "body_content")
            if key in resolved_values
        }
        for field, prefix in _HTTP_ROWS:
            for position, row in enumerate(getattr(service, field).all()):
                if f"{prefix}_{row.id}" in resolved_values:
                    values[f"{field}.{position}"] = resolved_values[
                        f"{prefix}_{row.id}"
                    ]
        self._check_request(action, service, values)
        return values

    def _check_request(
        self,
        action: AgentAction,
        service: CoreHTTPRequestService,
        values: dict[str, str],
    ) -> None:
        url = values["url"]
        try:
            parts = urlsplit(url)
            # Reading the port checks it, which parsing doesn't.
            valid = parts.scheme in ("http", "https") and parts.hostname
            valid = valid and (parts.port is None or parts.port > 0)
        except ValueError:
            valid = False
        if not valid:
            raise ToolInputError(
                "The address must be a full URL starting with http:// or https://."
            )
        if len(url.encode()) > HTTP_ACTION_MAX_URL_BYTES:
            raise ToolInputError(
                f"The address is longer than {HTTP_ACTION_MAX_URL_BYTES // 1024} KB."
            )
        # The keys of the rows that are sent count too, as the builder may add
        # as many as they like.
        keys = [
            row.key
            for field, prefix in _HTTP_ROWS
            for position, row in enumerate(getattr(service, field).all())
            if f"{field}.{position}" in values
        ]
        if sum(len(text.encode()) for text in [*values.values(), *keys]) > (
            HTTP_ACTION_MAX_REQUEST_BYTES
        ):
            raise ToolInputError(
                f"The request is larger than {HTTP_ACTION_MAX_REQUEST_BYTES // 1024}"
                " KB."
            )
        for position, row in enumerate(service.headers.all()):
            value = values[f"headers.{position}"]
            if _LINE_BREAK.search(row.key + value):
                raise ToolInputError(f'The header "{row.key}" contains a line break.')
            try:
                # What HTTP sends a header name and value as.
                row.key.encode("ascii")
                value.encode("latin-1")
            except UnicodeEncodeError as exc:
                raise ToolInputError(
                    f'The header "{row.key}" contains a character a header can\'t '
                    f"carry: {exc.object[exc.start]}.",
                    hint="Use plain ASCII text in headers.",
                ) from exc
        body = values.get("body_content")
        if service.body_type == BODY_TYPE.JSON and body:
            try:
                json.loads(
                    body,
                    strict=False,
                    parse_constant=_refuse_constant,
                    parse_float=_parse_finite_float,
                )
            except (json.JSONDecodeError, ValueError) as exc:
                raise ToolInputError(
                    f"The request body is not valid JSON: {exc}.",
                    hint="Send the body as one JSON value, with every string "
                    "quoted and escaped.",
                ) from exc
        # A URL that mixes fixed text with an input may carry a key itself.
        if not self._is_shown(service, "url") or any(
            value and not self._is_shown(service, key)
            for key, value in values.items()
            if key != "url"
        ):
            self._check_fixed_host(action, service, parts)

    def _check_fixed_host(self, action, service, parts) -> None:
        """
        A request carrying values the approver doesn't read must go where the
        builder pointed it, or the model could send an API key elsewhere. Its
        host is resolved with every input empty and must be the same.
        """

        if not _reads_tool_input(service.url):
            return
        fixed = self._get_fixed_url(action, service)
        try:
            same = fixed is not None and (
                fixed.scheme,
                fixed.hostname,
                fixed.port,
            ) == (parts.scheme, parts.hostname, parts.port)
        except ValueError:
            same = False
        if not same:
            # The builder is told when no fixed host can be read at all, so
            # here the model changed it.
            raise ToolInputError(
                "This request can only be sent to "
                f"{fixed.hostname if fixed else 'the server the action names'}.",
                hint="Change only the part of the address the inputs describe.",
            )

    def _get_fixed_url(self, action, service) -> SplitResult | None:
        """
        :return: The URL resolved with every input empty, when it names a host.
        """

        try:
            fixed = urlsplit(
                ensure_string(
                    resolve_formula(
                        service.url,
                        formula_runtime_function_registry,
                        AgentActionDispatchContext(
                            workspace=action.agent.workspace,
                            tool_inputs={item["id"]: "" for item in action.inputs},
                        ),
                    )
                )
            )
            return fixed if fixed.hostname else None
        # The empty-input URL may not resolve, or not parse.
        except Exception:
            return None

    def get_held_values(
        self, action: AgentAction, resolved_values: dict[str, Any]
    ) -> dict[str, Any]:
        service = action.service.specific
        return {
            key: value
            for key, value in resolved_values.items()
            if self._is_shown(service, key)
        }

    def complete_held_values(
        self,
        action: AgentAction,
        arguments: dict[str, Any],
        held_values: dict[str, Any],
    ) -> dict[str, Any]:
        return {**self.prepare(action, arguments), **held_values}

    def get_preview_values(
        self, service: CoreHTTPRequestService, resolved_values: dict[str, Any]
    ) -> dict[str, Any]:
        def shown(key):
            return (
                resolved_values[key] if self._is_shown(service, key) else HIDDEN_VALUE
            )

        url = resolved_values["url"]
        values = {
            "http_method": service.http_method,
            "url": url if self._is_shown(service, "url") else _hide_url_secrets(url),
        }
        for field, _ in _HTTP_ROWS:
            rows = getattr(service, field).all()
            values[field] = {
                row.key: shown(f"{field}.{position}")
                for position, row in enumerate(rows)
                if f"{field}.{position}" in resolved_values
            }
        values["body_type"] = service.body_type
        if "body_content" in resolved_values:
            values["body_content"] = shown("body_content")
        # A request without any of a kind of row reads better without its name.
        return {key: value for key, value in values.items() if value != {}}

    def get_preview(
        self,
        action: AgentAction,
        resolved_values: dict[str, Any],
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Adds the inputs that no shown value is exactly, such as one the URL or a
        body mixes with fixed text, so that the approver reads every choice of
        the model.
        """

        preview = super().get_preview(action, resolved_values, arguments)
        service = action.service.specific
        shown = {self._shown_input(service, key) for key in resolved_values}
        inputs = {
            item["name"]: arguments[item["name"]]
            for item in action.inputs
            if item["id"] not in shown and item["name"] in arguments
        }
        if inputs:
            preview["values"]["inputs"] = inputs
        return preview

    def _get_formula(self, service: CoreHTTPRequestService, key: str) -> dict:
        """
        :param key: A resolved value's key.
        :return: The stored formula the value resolves.
        """

        if key in ("url", "body_content"):
            return getattr(service, key)
        field, position = key.split(".")
        return list(getattr(service, field).all())[int(position)].value

    def _shown_input(self, service: CoreHTTPRequestService, key: str) -> str | None:
        """
        :param key: A resolved value's key.
        :return: The ID of the input the value is exactly, which the approver
            then reads as the model chose it.
        """

        formula = self._get_formula(service, key)
        if formula.get("mode") == BASEROW_FORMULA_MODE_RAW:
            return None
        match = _SINGLE_INPUT.match((formula.get("formula") or "").strip())
        return match.group(2) if match else None

    def _is_shown(self, service: CoreHTTPRequestService, key: str) -> bool:
        """
        :param key: A resolved value's key.
        :return: Whether the approver reads the value: only when it is exactly
            one input.
        """

        return self._shown_input(service, key) is not None

    def dispatch(
        self, action: AgentAction, resolved_values: dict[str, Any]
    ) -> DispatchResult:
        """
        Send the request, with each row's value given to the row now at its
        position. Failures are explained: whether the model can fix them, or
        what happened to the request.
        """

        service = action.service.specific
        values = {
            key: resolved_values[key]
            for key in ("url", "body_content")
            if key in resolved_values
        }
        for field, prefix in _HTTP_ROWS:
            for position, row in enumerate(getattr(service, field).all()):
                if f"{field}.{position}" in resolved_values:
                    values[f"{prefix}_{row.id}"] = resolved_values[
                        f"{field}.{position}"
                    ]
        try:
            result = super().dispatch(action, values)
        except AddressNotAllowedDispatchException as exc:
            raise ToolInputError(
                "This address can't be called from this Baserow instance."
            ) from exc
        except RedirectNotAllowedDispatchException as exc:
            raise ToolFailedError(
                "The API redirected the request to another server, so it wasn't "
                "followed.",
                hint="Say where the API redirects only if the answer shows it. Use "
                "the address the user or the action gives.",
            ) from exc
        except ResponseTooLargeDispatchException as exc:
            raise ToolFailedError(
                "The API answered with more than this Baserow instance accepts."
            ) from exc
        except RuntimeDispatchException as exc:
            if isinstance(
                exc.__cause__,
                (
                    request_exceptions.InvalidURL,
                    request_exceptions.InvalidHeader,
                    request_exceptions.InvalidJSONError,
                    request_exceptions.MissingSchema,
                ),
            ):
                raise ToolInputError(
                    "The request can't be sent: its address, a header or its "
                    "body is malformed."
                ) from exc
            raise ToolFailedError(
                "The request didn't reach the API or got no complete answer.",
                hint="Say that the API couldn't be reached. Try again only if "
                "the user asks to.",
            ) from exc
        if result.data.get("timed_out"):
            raise ToolFailedError(
                f"The API didn't answer within {service.timeout} seconds.",
                hint="The API may still have done what was asked. Check before "
                "calling it again.",
            )
        return result

    def get_tool_result(self, action: AgentAction, result: DispatchResult) -> Any:
        """
        :return: The status, content type and body of the response. A body longer
            than ``HTTP_ACTION_MAX_RESULT_CHARACTERS`` comes back as the start
            of its text, as the model reads it in every later turn.
        """

        data = result.data
        answer = {
            "status_code": data["status_code"],
            "content_type": data["headers"].get("content-type", ""),
            "body": data["body"],
            "body_omitted": data["body_omitted"],
        }
        # Measured as the model reads it: the raw body leaves the empty
        # items of a list out.
        body = data["body"]
        text = body if isinstance(body, str) else json.dumps(body)
        if len(text) > HTTP_ACTION_MAX_RESULT_CHARACTERS:
            answer["body"] = text[:HTTP_ACTION_MAX_RESULT_CHARACTERS]
            answer["body_truncated"] = True
        return answer


def _reads_tool_input(value: dict[str, Any]) -> bool:
    """
    :param value: A stored formula.
    :return: Whether it may read what the model provides.
    """

    return value.get("mode") != BASEROW_FORMULA_MODE_RAW and "tool_input." in (
        value.get("formula") or ""
    )


def _refuse_constant(name: str) -> None:
    raise ValueError(f"{name} is not allowed")


def _parse_finite_float(text: str) -> float:
    # A number too large for a float reads as infinity, which can't be sent.
    value = float(text)
    if not math.isfinite(value):
        raise ValueError(f"{text} is too large")
    return value


def _hide_url_secrets(url: str) -> str:
    """
    :param url: A URL the builder fixed, at least in part.
    :return: The URL with its user, password, path and query values hidden,
        where a key or a webhook token sits. The server it goes to stays
        readable, and the inputs the URL reads are listed apart.
    """

    parts = urlsplit(url)
    netloc = parts.netloc
    if "@" in netloc:
        netloc = f"{HIDDEN_VALUE}@{netloc.rsplit('@', 1)[1]}"
    path = parts.path if parts.path in ("", "/") else f"/{HIDDEN_VALUE}"
    query = "&".join(
        f"{quote_plus(key)}={HIDDEN_VALUE}"
        for key, _ in parse_qsl(parts.query, keep_blank_values=True)
    )
    return urlunsplit(
        parts._replace(netloc=netloc, path=path, query=query, fragment="")
    )
