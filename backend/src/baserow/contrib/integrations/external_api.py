import time
from typing import Any, Dict, List, Optional, Tuple, TypedDict

from loguru import logger
from requests import exceptions as request_exceptions
from rest_framework import serializers

from advocate.exceptions import UnacceptableAddressException
from baserow.contrib.integrations.utils import send_http_request
from baserow.core.formula import BaserowFormulaObject
from baserow.core.formula.validator import ensure_string
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.exceptions import (
    AddressNotAllowedDispatchException,
    RemoteRefusedDispatchException,
    ResponseTooLargeDispatchException,
    ServiceImproperlyConfiguredDispatchException,
    UnexpectedDispatchException,
    UnreachableAddressDispatchException,
)
from baserow.core.services.registries import DispatchTypes, ServiceType
from baserow.core.services.types import DispatchResult, FormulaToResolve, ServiceDict

JsonBody = Any


def split_addresses(value: str) -> List[str]:
    """
    Splits a comma or semicolon separated list of email addresses, as a person
    types them or a formula joins them.
    """

    return [
        part.strip()
        for part in (value or "").replace(";", ",").split(",")
        if part.strip()
    ]


def is_date_only(value: str) -> bool:
    """A bare `YYYY-MM-DD` means an all-day event for every calendar API."""

    return len(value) == 10 and value[4] == "-" and value[7] == "-"


class ExternalAPIServiceType(ServiceType):
    """
    An action that calls a third party's JSON API with an integration's
    credentials. Subclasses name their model's formula and plain fields and
    the shape of their answer; the serializer, export dict, formula resolution
    and schema follow from that, and `request_json` turns transport trouble
    into the dispatch exceptions the products already show.
    """

    dispatch_types = [DispatchTypes.ACTION]
    is_external = True

    # Shown to the user in error messages.
    provider_name = "the remote service"
    request_timeout_seconds = 10
    # Requests one dispatch may make, which bounds the click budget.
    request_count = 1

    # Model fields the user writes as formulas; resolved to strings.
    formula_fields: List[str] = []
    # Other model fields the user configures (ints, choices).
    plain_fields: List[str] = []
    # JSON schema properties of the dispatch answer.
    schema_properties: Dict[str, Any] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if getattr(cls, "model_class", None) is None:
            return
        fields = ["integration_id", *cls.formula_fields, *cls.plain_fields]
        cls.allowed_fields = fields
        cls.serializer_field_names = fields
        cls.public_serializer_field_names = fields
        cls.simple_formula_fields = list(cls.formula_fields)
        cls.SerializedDict = TypedDict(
            f"{cls.__name__}Dict",
            {
                **ServiceDict.__annotations__,
                **{name: BaserowFormulaObject for name in cls.formula_fields},
                **{name: Any for name in cls.plain_fields},
            },
        )

    @property
    def serializer_field_overrides(self):
        from baserow.core.formula.serializers import FormulaSerializerField

        overrides = {
            "integration_id": serializers.IntegerField(
                required=False,
                allow_null=True,
                help_text=f"The id of the {self.provider_name} integration.",
            )
        }
        for name in self.formula_fields:
            overrides[name] = FormulaSerializerField(
                help_text=self.model_class._meta.get_field(name).help_text
            )
        return overrides

    @property
    def public_serializer_field_overrides(self):
        return self.serializer_field_overrides

    def formulas_to_resolve(self, service) -> List[FormulaToResolve]:
        return [
            FormulaToResolve(
                name, getattr(service, name), ensure_string, f'property "{name}"'
            )
            for name in self.formula_fields
        ]

    def get_integration(self, service):
        integration = service.integration
        if integration is None or integration.get_type().type != self.integration_type:
            raise ServiceImproperlyConfiguredDispatchException(
                f"This action has no {self.provider_name} integration selected."
            )
        return integration.specific

    def request_json(
        self,
        dispatch_context: DispatchContext,
        method: str,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Any = None,
        data: Any = None,
    ) -> Tuple[int, JsonBody]:
        """
        Sends one request and returns its status and decoded JSON body (None
        for an empty body). A 4xx/5xx answer is a `RemoteRefusedDispatchException`
        carrying the provider's own message, so the person sees why.
        """

        deadline = time.monotonic() + (
            self.request_timeout_seconds * dispatch_context.external_request_timeouts
        )
        try:
            response = send_http_request(
                method,
                url,
                deadline=deadline,
                operation_timeout=self.request_timeout_seconds,
                headers=headers,
                params=params,
                json=json,
                data=data,
                allow_redirects=False,
            )
        except ResponseTooLargeDispatchException:
            raise
        except UnacceptableAddressException as e:
            raise AddressNotAllowedDispatchException(
                f"The {self.provider_name} address is not allowed by this installation."
            ) from e
        except request_exceptions.Timeout as e:
            raise UnreachableAddressDispatchException(
                f"{self.provider_name} did not answer in time."
            ) from e
        except request_exceptions.RequestException as e:
            raise UnexpectedDispatchException(
                f"The request to {self.provider_name} failed: {type(e).__name__}."
            ) from e
        except Exception as e:  # noqa: BLE001
            # The type name only: the frame's locals hold the credentials.
            logger.error(
                "Error while calling {provider}: {exception}.",
                provider=self.provider_name,
                exception=type(e).__name__,
            )
            raise UnexpectedDispatchException(
                f"Unknown error: {type(e).__name__}"
            ) from e

        body = None
        if response.content:
            try:
                body = response.json()
            except ValueError:
                body = None
        if response.status_code >= 400:
            raise RemoteRefusedDispatchException(
                self.describe_error(response.status_code, body)
            )
        return response.status_code, body

    def describe_error(self, status_code: int, body: JsonBody) -> str:
        """
        The provider's own explanation, in the shapes Google, Microsoft Graph
        and Jira answer with, with a hint for the two causes a person can fix
        in the integration settings.
        """

        message = ""
        if isinstance(body, dict):
            error = body.get("error")
            if isinstance(error, dict):
                message = error.get("message") or ""
            elif isinstance(error, str):
                message = body.get("error_description") or error
            if not message and isinstance(body.get("errorMessages"), list):
                message = "; ".join(str(m) for m in body["errorMessages"])
            if not message and isinstance(body.get("errors"), dict):
                message = "; ".join(f"{k}: {v}" for k, v in body["errors"].items())
            if not message and isinstance(body.get("message"), str):
                message = body["message"]
        if status_code in (401, 403):
            hint = " Check the credentials of the integration" + (
                " and reconnect it." if self.reconnectable else "."
            )
        else:
            hint = ""
        prefix = f"{self.provider_name} answered {status_code}"
        return f"{prefix}: {message}.{hint}" if message else f"{prefix}.{hint}"

    # Whether a 401 can be fixed by connecting the account again.
    reconnectable = False

    def dispatch_transform(self, data: Any) -> DispatchResult:
        return DispatchResult(data=data)

    def max_dispatch_seconds(self, service) -> int:
        # Each request gets its timeout for the connect and again for the read,
        # as the Slack action reasons; the token refresh is one more request.
        return self.request_timeout_seconds * 2 * self.request_count

    def enhance_queryset(self, queryset):
        return super().enhance_queryset(queryset).select_related("integration")

    def get_schema_name(self, service) -> str:
        return f"{type(self).__name__.removesuffix('ServiceType')}{service.id}Schema"

    def generate_schema(
        self, service, allowed_fields: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        properties = {
            name: definition
            for name, definition in self.schema_properties.items()
            if allowed_fields is None or name in allowed_fields
        }
        return {
            "title": self.get_schema_name(service),
            "type": "object",
            "properties": properties,
        }


def string_property(title: str) -> Dict[str, Any]:
    return {"type": "string", "title": title}


def boolean_property(title: str) -> Dict[str, Any]:
    return {"type": "boolean", "title": title}


def number_property(title: str) -> Dict[str, Any]:
    return {"type": "number", "title": title}


def array_property(title: str, item_properties: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "array",
        "title": title,
        "items": {"type": "object", "properties": item_properties},
    }
