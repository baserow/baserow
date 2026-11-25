import json
import math
import re
from typing import Any
from urllib.parse import SplitResult, parse_qsl, quote_plus, urlsplit, urlunsplit
from uuid import uuid4

from django.conf import settings

from requests import exceptions as request_exceptions

from baserow.contrib.agent.constants import ACTION_MAX_RESULT_CHARACTERS
from baserow.contrib.agent.models import AgentAction
from baserow.contrib.integrations.core.constants import BODY_TYPE, HTTP_METHOD
from baserow.contrib.integrations.core.models import (
    CoreHTTPRequestService,
    CoreSMTPEmailService,
)
from baserow.contrib.integrations.local_baserow.mixins import (
    LocalBaserowTableServiceFilterableMixin,
    LocalBaserowTableServiceSearchableMixin,
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
from baserow.core.services.models import Service
from baserow.core.services.types import DispatchResult
from baserow.core.tools.errors import ToolFailedError, ToolInputError
from baserow.core.types import Subject

from .data_providers import AgentActionDispatchContext
from .formulas import reads_only_inputs
from .inputs import AgentActionInput
from .registries import AgentActionDefaults, AgentActionType

HTTP_ACTION_MAX_REQUEST_BYTES = 64 * 1024
"""The most a call may send: its URL, headers, query parameters and body."""

HTTP_ACTION_MAX_URL_BYTES = 8 * 1024
"""The longest URL a call may send, which servers commonly refuse past this."""

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


def bound_input(
    name: str, input_type: str, description: str, required: bool = True
) -> tuple[AgentActionInput, BaserowFormulaObject]:
    """
    Make an input for the starter of a new action, together with the formula
    that reads it. The starter lists the input under ``inputs`` and gives the
    formula to the service field the model should fill, so a new action works
    without its builder binding anything. Each call makes an input with an ID
    of its own, as formulas refer to an input by ID.

    :param name: The name the model fills the input by.
    :param input_type: One of the input types.
    :param description: What the model is told to fill in.
    :param required: Whether the model must fill it in.
    :return: A new input of a starter, and the formula of a service field that
        is exactly that input.
    """

    input_id = str(uuid4())
    return (
        {
            "id": input_id,
            "name": name,
            "type": input_type,
            "description": description,
            "required": required,
        },
        BaserowFormulaObject.create(f"get('tool_input.{input_id}')", mode="simple"),
    )


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

    def get_configuration_errors(
        self, action: AgentAction, identity: Subject | None = None
    ) -> dict[str, str]:
        # A row is reported by the list it sits in, which the form labels.
        service = action.service.specific
        lists = {
            f"{prefix}_{row.id}": field
            for field, prefix in _HTTP_ROWS
            for row in getattr(service, field).all()
        }
        errors = {
            lists.get(key, key): error
            for key, error in super().get_configuration_errors(action, identity).items()
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
        self,
        action: AgentAction,
        resolved_values: dict[str, Any],
        identity: Subject | None = None,
        arguments: dict[str, Any] | None = None,
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
            result = super().dispatch(action, values, identity, arguments)
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
            than ``ACTION_MAX_RESULT_CHARACTERS`` comes back as the start
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
        if len(text) > ACTION_MAX_RESULT_CHARACTERS:
            answer["body"] = text[:ACTION_MAX_RESULT_CHARACTERS]
            answer["body_truncated"] = True
        return answer


class LocalBaserowAgentActionType(AgentActionType):
    """
    Hosts a Local Baserow service type whose service works on a table, as the
    Agent's run identity.
    """

    acts_as_run_identity = True
    filters_read_inputs = True

    def get_preview_values(
        self, service: Service, resolved_values: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "table": service.table.name if service.table_id else None,
            **resolved_values,
        }

    def get_preview(
        self,
        action: AgentAction,
        resolved_values: dict[str, Any],
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Adds the call's inputs when the service has formulas that are only
        resolved while the call is sent, so that the approver reads what they use.
        """

        preview = super().get_preview(action, resolved_values, arguments)
        if arguments and self._get_late_formulas(action.service.specific):
            preview["values"]["inputs"] = arguments
        return preview

    def _get_late_formulas(
        self, service: Service
    ) -> dict[str, list[BaserowFormulaObject]]:
        """
        :param service: The action's specific service.
        :return: The formulas the service only resolves while a call is sent, by
            the field they are of: its filter values and its search query, when
            it has them.
        """

        formulas = {}
        if isinstance(self.service_type, LocalBaserowTableServiceFilterableMixin):
            formulas["filters"] = [
                BaserowFormulaObject.to_formula(service_filter.value)
                for service_filter in service.service_filters_with_untrashed_fields
            ]
        if isinstance(self.service_type, LocalBaserowTableServiceSearchableMixin):
            formulas["search_query"] = [
                BaserowFormulaObject.to_formula(service.search_query)
            ]
        written = {
            field: [formula for formula in field_formulas if formula["formula"]]
            for field, field_formulas in formulas.items()
        }
        return {field: used for field, used in written.items() if used}

    def get_configuration_errors(
        self, action: AgentAction, identity: Subject | None = None
    ) -> dict[str, str]:
        return self.get_configuration_errors_by_action([action], identity)[action.id]

    def get_configuration_errors_by_action(
        self, actions: list[AgentAction], identity: Subject | None = None
    ) -> dict[int, dict[str, str]]:
        """
        Check whether the identity can read the actions' tables in one permission
        check, so that it doesn't cost a query per action.
        """

        if not actions:
            return {}
        readable_table_ids = self.service_type.get_subject_readable_table_ids(
            [action.service.specific for action in actions],
            identity,
            actions[0].agent.workspace,
        )
        return {
            action.id: self._get_configuration_errors(
                action, identity, readable_table_ids
            )
            for action in actions
        }

    def _get_configuration_errors(
        self,
        action: AgentAction,
        identity: Subject | None,
        readable_table_ids: set[int],
    ) -> dict[str, str]:
        """
        Also require a table the run identity can read, and filters and a search
        query that only read the action's inputs.

        :param action: The action, with its agent and workspace.
        :param identity: The Agent's run identity, or None.
        :param readable_table_ids: The ids of the tables the identity may read.
        :return: An error code by field, empty when the action can be called.
        """

        errors = super().get_configuration_errors(action, identity)
        service = action.service.specific
        if not service.table_id:
            errors["table_id"] = "required"
        elif identity is not None and service.table_id not in readable_table_ids:
            errors["table_id"] = "unavailable"
        for field, formulas in self._get_late_formulas(service).items():
            if not all(
                reads_only_inputs(formula, action.inputs) for formula in formulas
            ):
                errors[field] = "invalid"
        return errors


class LocalBaserowCreateRowAgentActionType(LocalBaserowAgentActionType):
    type = "local_baserow_create_row"
    service_type_name = "local_baserow_upsert_row"

    def get_defaults(self) -> AgentActionDefaults:
        return {
            "name": "create_row",
            "description": "Create a row in the table when the user asks to add "
            "or record something there.",
            "inputs": [],
            "service": {},
        }

    def get_formulas(self, service: Service) -> dict[str, BaserowFormulaObject]:
        """
        Read the formulas from the mappings the action was loaded with, as the
        service type would query them again for each action that is checked.
        """

        formulas = {
            f"field_{mapping.field_id}": BaserowFormulaObject.to_formula(mapping.value)
            for mapping in service.field_mappings.all()
            if not mapping.field.trashed
        }
        if service.row_id["formula"]:
            formulas["row_id"] = service.row_id
        return formulas

    def get_preview_values(
        self, service: Service, resolved_values: dict[str, Any]
    ) -> dict[str, Any]:
        """
        :return: The values written under the name of their field, apart from the
            rest of the request, which a field could be named like.
        """

        field_names = {
            f"field_{mapping.field_id}": mapping.field.name
            for mapping in service.field_mappings.select_related("field")
        }
        values = {
            key: value
            for key, value in resolved_values.items()
            if key not in field_names
        }
        values["fields"] = {
            name: resolved_values[key]
            for key, name in field_names.items()
            if key in resolved_values
        }
        return super().get_preview_values(service, values)


class LocalBaserowUpdateRowAgentActionType(LocalBaserowCreateRowAgentActionType):
    type = "local_baserow_update_row"

    def get_defaults(self) -> AgentActionDefaults:
        row_id, formula = bound_input(
            "row_id", "number", "The id of the row to update."
        )
        return {
            "name": "update_row",
            "description": "Update a row of the table when the user asks to "
            "change something there. You need the id of the row.",
            "inputs": [row_id],
            "service": {"row_id": formula},
        }

    def _get_configuration_errors(
        self,
        action: AgentAction,
        identity: Subject | None,
        readable_table_ids: set[int],
    ) -> dict[str, str]:
        errors = super()._get_configuration_errors(action, identity, readable_table_ids)
        # Without a row, the service would create one.
        if not action.service.specific.row_id["formula"]:
            errors["row_id"] = "required"
        return errors


class LocalBaserowDeleteRowAgentActionType(LocalBaserowAgentActionType):
    type = "local_baserow_delete_row"

    def get_defaults(self) -> AgentActionDefaults:
        row_id, formula = bound_input(
            "row_id", "number", "The id of the row to delete."
        )
        return {
            "name": "delete_row",
            "description": "Delete a row of the table when the user asks to "
            "remove it. You need the id of the row.",
            "inputs": [row_id],
            "service": {"row_id": formula},
        }

    def get_tool_result(self, action: AgentAction, result: DispatchResult) -> Any:
        # The service answers nothing once the row is gone.
        return {"deleted": True}


class LocalBaserowGetRowAgentActionType(LocalBaserowAgentActionType):
    type = "local_baserow_get_row"
    changes_data = False

    def get_defaults(self) -> AgentActionDefaults:
        row_id, formula = bound_input("row_id", "number", "The id of the row to read.")
        return {
            "name": "get_row",
            "description": "Read one row of the table by its id.",
            "inputs": [row_id],
            "service": {"row_id": formula},
        }


class LocalBaserowListRowsAgentActionType(LocalBaserowAgentActionType):
    type = "local_baserow_list_rows"
    changes_data = False

    def get_defaults(self) -> AgentActionDefaults:
        search, formula = bound_input(
            "search",
            "string",
            "Words the rows must contain. Leave it out to list the first rows.",
            required=False,
        )
        return {
            "name": "list_rows",
            "description": "List rows of the table, optionally only the ones "
            "that contain what you search for.",
            "inputs": [search],
            "service": {"search_query": formula},
        }


class LocalBaserowAggregateRowsAgentActionType(LocalBaserowAgentActionType):
    type = "local_baserow_aggregate_rows"
    changes_data = False

    def get_defaults(self) -> AgentActionDefaults:
        return {
            "name": "aggregate_rows",
            "description": "Calculate a summary of a field over the rows of the "
            "table, such as a count or a sum.",
            "inputs": [],
            "service": {},
        }


class SlackWriteMessageAgentActionType(AgentActionType):
    type = "slack_write_message"

    def get_defaults(self) -> AgentActionDefaults:
        text, formula = bound_input(
            "text", "string", "The complete message, ready to post as it is."
        )
        return {
            "name": "send_slack_message",
            "description": "Post a message to the Slack channel when the user "
            "asks to tell or notify the people there.",
            "inputs": [text],
            "service": {"text": formula},
        }

    def get_preview_values(
        self, service: Service, resolved_values: dict[str, Any]
    ) -> dict[str, Any]:
        return {"channel": service.channel, **resolved_values}


class AIAgentAgentActionType(AgentActionType):
    type = "ai_agent"
    changes_data = False

    def get_defaults(self) -> AgentActionDefaults:
        prompt, formula = bound_input(
            "prompt", "string", "The complete prompt for the other AI model."
        )
        return {
            "name": "ask_ai_model",
            "description": "Ask another AI model and read its answer.",
            "inputs": [prompt],
            "service": {"ai_prompt": formula},
        }


class StartWorkflowAgentActionType(AgentActionType):
    type = "start_workflow"

    def get_defaults(self) -> AgentActionDefaults:
        return {
            "name": "start_workflow",
            "description": "Start the automation workflow when the user asks "
            "for what it does.",
            "inputs": [],
            "service": {},
        }

    def get_preview_values(
        self, service: Service, resolved_values: dict[str, Any]
    ) -> dict[str, Any]:
        return {"workflow": service.workflow.name if service.workflow_id else None}

    def get_configuration_errors(
        self, action: AgentAction, identity: Subject | None = None
    ) -> dict[str, str]:
        """
        Also require a workflow of the Agent's workspace, which the service only
        checks when a call is sent.
        """

        errors = super().get_configuration_errors(action, identity)
        workflow = action.service.specific.workflow
        if workflow is not None and (
            workflow.trashed
            or workflow.automation.trashed
            or workflow.automation.workspace_id != action.agent.workspace_id
        ):
            errors["workflow_id"] = "unavailable"
        return errors


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
