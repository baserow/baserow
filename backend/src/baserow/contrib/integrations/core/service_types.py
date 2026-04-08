import json
import socket
import uuid
from datetime import datetime
from smtplib import SMTPAuthenticationError, SMTPConnectError, SMTPNotSupportedError
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db import router
from django.db.models import Q, QuerySet
from django.urls import path
from django.utils import timezone
from django.utils.translation import gettext as _

from genson import SchemaBuilder
from loguru import logger
from requests import exceptions as request_exceptions
from rest_framework import serializers

from advocate.connection import UnacceptableAddressException
from baserow.config.celery import app as celery_app
from baserow.contrib.automation.nodes.exceptions import (
    AutomationNodeMisconfiguredService,
)
from baserow.contrib.integrations.core.api.webhooks.views import CoreHTTPTriggerView
from baserow.contrib.integrations.core.constants import (
    BODY_TYPE,
    HTTP_METHOD,
    PERIODIC_INTERVAL_CHOICES,
    PERIODIC_INTERVAL_MINUTE,
)
from baserow.contrib.integrations.core.exceptions import (
    CoreHTTPTriggerServiceDoesNotExist,
    CoreHTTPTriggerServiceMethodNotAllowed,
)
from baserow.contrib.integrations.core.integration_types import SMTPIntegrationType
from baserow.contrib.integrations.core.models import (
    CoreHTTPRequestService,
    CoreHTTPTriggerService,
    CoreIteratorService,
    CorePeriodicService,
    CoreRouterService,
    CoreRouterServiceEdge,
    CoreSMTPEmailService,
    HTTPFormData,
    HTTPHeader,
    HTTPQueryParam,
)
from baserow.contrib.integrations.core.utils import calculate_next_periodic_run
from baserow.contrib.integrations.utils import get_http_request_function
from baserow.core.formula.types import BaserowFormulaObject
from baserow.core.formula.validator import (
    ensure_array,
    ensure_boolean,
    ensure_email,
    ensure_string,
)
from baserow.core.registries import ImportExportConfig
from baserow.core.registry import Instance
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.exceptions import (
    InvalidContextContentDispatchException,
    ServiceImproperlyConfiguredDispatchException,
    UnexpectedDispatchException,
)
from baserow.core.services.models import Service
from baserow.core.services.registries import (
    DispatchTypes,
    ListServiceTypeMixin,
    ServiceType,
    TriggerServiceTypeMixin,
)
from baserow.core.services.types import DispatchResult, FormulaToResolve, ServiceDict
from baserow.version import VERSION as BASEROW_VERSION


class CoreServiceType(ServiceType):
    """
    The base class for all core service types. Currently only used
    as a way to differentiate core and non-core service types.
    """


class CoreHTTPRequestServiceType(CoreServiceType):
    type = "http_request"
    model_class = CoreHTTPRequestService
    dispatch_types = [DispatchTypes.ACTION]

    allowed_fields = [
        "http_method",
        "url",
        "body_type",
        "body_content",
        "timeout",
    ]

    _serializer_field_names = [
        "http_method",
        "url",
        "headers",
        "query_params",
        "form_data",
        "body_type",
        "body_content",
        "timeout",
    ]

    request_serializer_field_names = [
        "http_method",
        "url",
        "headers",
        "query_params",
        "form_data",
        "body_type",
        "body_content",
        "timeout",
    ]

    class SerializedDict(ServiceDict):
        http_method: str
        url: str
        headers: List[Dict[str, str]]
        query_params: List[Dict[str, str]]
        form_data: List[Dict[str, str]]
        body_type: str
        body_content: str
        timeout: int

    simple_formula_fields = ["body_content", "url"]

    @property
    def serializer_field_names(self):
        return self._serializer_field_names + self.default_serializer_field_names

    @property
    def serializer_field_overrides(self):
        from baserow.contrib.integrations.core.api.serializers import (
            HTTPFormDataSerializer,
            HTTPHeaderSerializer,
            HTTPQueryParamSerializer,
        )
        from baserow.core.formula.serializers import FormulaSerializerField

        return {
            "http_method": serializers.ChoiceField(
                choices=HTTP_METHOD.choices,
                help_text=CoreHTTPRequestService._meta.get_field(
                    "http_method"
                ).help_text,
                required=False,
                default=HTTP_METHOD.GET,
            ),
            "url": FormulaSerializerField(
                help_text=CoreHTTPRequestService._meta.get_field("url").help_text,
                default="",
            ),
            "body_type": serializers.ChoiceField(
                choices=BODY_TYPE.choices,
                help_text=CoreHTTPRequestService._meta.get_field("body_type").help_text,
                required=False,
                default=BODY_TYPE.NONE,
            ),
            "body_content": FormulaSerializerField(
                help_text=CoreHTTPRequestService._meta.get_field(
                    "body_content"
                ).help_text,
                default="",
            ),
            "headers": HTTPHeaderSerializer(
                many=True,
                required=False,
                help_text="The headers for the request.",
            ),
            "query_params": HTTPQueryParamSerializer(
                many=True,
                required=False,
                help_text="The query params for the request.",
            ),
            "form_data": HTTPFormDataSerializer(
                many=True,
                required=False,
                help_text="The form data for the request.",
            ),
            "timeout": serializers.IntegerField(
                required=False,
                min_value=1,
                max_value=120,
                help_text=CoreHTTPRequestService._meta.get_field("timeout").help_text,
            ),
        }

    def after_create(
        self,
        instance: CoreHTTPRequestService,
        values: Dict,
    ):
        """Handles related fields"""

        if "form_data" in values:
            bulk_form_data = []
            # Bulk delete the existing ones on the service.
            instance.form_data.all().delete()

            for fdata in values["form_data"]:
                bulk_form_data.append(
                    HTTPFormData(
                        service=instance,
                        key=fdata["key"],
                        value=fdata["value"],
                    )
                )

            HTTPFormData.objects.bulk_create(bulk_form_data)

        if "headers" in values:
            bulk_headers = []
            # Bulk delete the existing headers on the service.
            instance.headers.all().delete()

            for header in values["headers"]:
                bulk_headers.append(
                    HTTPHeader(
                        service=instance,
                        key=header["key"],
                        value=header["value"],
                    )
                )

            HTTPHeader.objects.bulk_create(bulk_headers)

        if "query_params" in values:
            bulk_query_params = []
            # Bulk delete the existing headers on the service.
            instance.query_params.all().delete()

            for header in values["query_params"]:
                bulk_query_params.append(
                    HTTPQueryParam(
                        service=instance,
                        key=header["key"],
                        value=header["value"],
                    )
                )

            HTTPQueryParam.objects.bulk_create(bulk_query_params)

    def after_update(
        self,
        instance,
        values,
        changes: Dict[str, Tuple],
    ):
        return self.after_create(instance, values)

    def formula_generator(
        self, service: ServiceType
    ) -> Generator[str | Instance, str, None]:
        """Handles related fields"""

        yield from super().formula_generator(service)

        # Return form_data formulas
        for fdata in service.form_data.all():
            new_formula = yield BaserowFormulaObject.to_formula(fdata.value)
            if new_formula is not None:
                fdata.value = new_formula
                yield fdata

        # Return headers formulas
        for header in service.headers.all():
            new_formula = yield BaserowFormulaObject.to_formula(header.value)
            if new_formula is not None:
                header.value = new_formula
                yield header

        # Return headers formulas
        for query_param in service.query_params.all():
            new_formula = yield BaserowFormulaObject.to_formula(query_param.value)
            if new_formula is not None:
                query_param.value = new_formula
                yield query_param

    def extract_properties(
        self, service: Service, path: List[str], **kwargs
    ) -> List[str]:
        """Returns the first path element if any"""

        if path:
            return [path[0]]

        return []

    def serialize_property(
        self,
        service: CoreHTTPRequestService,
        prop_name: str,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        """
        Handles related fields.
        """

        if prop_name == "form_data":
            return [
                {
                    "key": m.key,
                    "value": m.value,
                }
                for m in service.form_data.all()
            ]

        if prop_name == "headers":
            return [
                {
                    "key": m.key,
                    "value": m.value,
                }
                for m in service.headers.all()
            ]

        if prop_name == "query_params":
            return [
                {
                    "key": m.key,
                    "value": m.value,
                }
                for m in service.query_params.all()
            ]

        return super().serialize_property(
            service, prop_name, files_zip=files_zip, storage=storage, cache=cache
        )

    def create_instance_from_serialized(
        self,
        serialized_values,
        id_mapping,
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ):
        """
        Responsible for creating related data (headers, query params, form_data).
        """

        headers = serialized_values.pop("headers", [])
        query_params = serialized_values.pop("query_params", [])
        form_data = serialized_values.pop("form_data", [])

        service = super().create_instance_from_serialized(
            serialized_values,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

        HTTPFormData.objects.bulk_create(
            [
                HTTPFormData(
                    **fdata,
                    service=service,
                )
                for fdata in form_data
            ]
        )

        HTTPHeader.objects.bulk_create(
            [
                HTTPHeader(
                    **header,
                    service=service,
                )
                for header in headers
            ]
        )

        HTTPQueryParam.objects.bulk_create(
            [
                HTTPQueryParam(
                    **query_param,
                    service=service,
                )
                for query_param in query_params
            ]
        )

        return service

    def enhance_queryset(self, queryset):
        return (
            super()
            .enhance_queryset(queryset)
            .prefetch_related("headers", "query_params", "form_data")
        )

    def get_schema_name(self, service: CoreHTTPRequestService) -> str:
        return f"HTTPRequest{service.id}Schema"

    def generate_schema(
        self,
        service: CoreHTTPRequestService,
        allowed_fields: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Generates the schema for the request response.
        """

        properties = {}

        if (allowed_fields is None or "body" in allowed_fields) and service.sample_data:
            schema_builder = SchemaBuilder()
            schema_builder.add_object(
                service.sample_data.get("data", {}).get("body", {})
            )
            schema = schema_builder.to_schema()

            properties |= {
                "body": schema
                | {
                    "title": "Body",
                }
            }

        if allowed_fields is None or "raw_body" in allowed_fields:
            properties.update(
                **{
                    "raw_body": {
                        "type": "string",
                        "title": "Raw body",
                    },
                },
            )

        if allowed_fields is None or "headers" in allowed_fields:
            schema = {}
            if service.sample_data:
                schema_builder = SchemaBuilder()
                schema_builder.add_object(
                    service.sample_data.get("data", {}).get("headers", {})
                )
                schema = schema_builder.to_schema()

            properties.update(
                **{
                    "headers": {
                        "type": "object",
                        "properties": {
                            "Content-Type": {
                                "type": "string",
                                "description": "The MIME type of the response body",
                            },
                            "Content-Length": {
                                "type": "number",
                                "description": "The length of the response body in octets (8-bit bytes)",
                            },
                            "ETag": {
                                "type": "string",
                                "description": "An identifier for a specific version of "
                                "a resource",
                            },
                        },
                        "title": "Headers",
                    }
                    | schema,
                },
            )

        if allowed_fields is None or "status_code" in allowed_fields:
            properties.update(
                **{
                    "status_code": {
                        "type": "number",
                        "title": "Status code",
                    },
                },
            )

        return {
            "title": self.get_schema_name(service),
            "type": "object",
            "properties": properties,
        }

    def formulas_to_resolve(
        self, service: CoreHTTPRequestService
    ) -> list[FormulaToResolve]:
        formulas = [
            FormulaToResolve(
                "body_content",
                service.body_content,
                ensure_string,
                'property "body_content"',
            ),
            FormulaToResolve("url", service.url, ensure_string, 'property "URL"'),
        ]

        for fdata in service.form_data.all():
            formulas.append(
                FormulaToResolve(
                    f"form_data_{fdata.id}",
                    fdata.value,
                    ensure_string,
                    f'form data "{fdata.key}"',
                ),
            )

        for header in service.headers.all():
            formulas.append(
                FormulaToResolve(
                    f"header_{header.id}",
                    header.value,
                    ensure_string,
                    f'header "{header.key}"',
                ),
            )

        for param in service.query_params.all():
            formulas.append(
                FormulaToResolve(
                    f"param_{param.id}",
                    param.value,
                    ensure_string,
                    f'query parameter "{param.key}"',
                ),
            )

        return formulas

    def dispatch_data(
        self,
        service: CoreHTTPRequestService,
        resolved_values: Dict[str, Any],
        dispatch_context: DispatchContext,
    ) -> Any:
        """
        Sends the request to the endpoint using the given data.
        """

        body_content = resolved_values["body_content"]
        body_dict = {}

        if service.body_type == BODY_TYPE.JSON:  # JSON payload
            try:
                body_dict["json"] = json.loads(body_content) if body_content else None
            except json.JSONDecodeError as e:
                raise ServiceImproperlyConfiguredDispatchException(
                    "The body is not a valid JSON"
                ) from e
        elif service.body_type == BODY_TYPE.FORM:  # Form multipart payload
            body_dict["data"] = {
                f.key: resolved_values[f"form_data_{f.id}"]
                for f in service.form_data.all()
            }
        elif service.body_type == BODY_TYPE.RAW:  # Raw payload
            body_dict["data"] = body_content

        headers = {"user-agent": f"Baserow/{BASEROW_VERSION}/HTTPRequestService"} | {
            h.key: resolved_values[f"header_{h.id}"] for h in service.headers.all()
        }
        query_params = {
            q.key: resolved_values[f"param_{q.id}"] for q in service.query_params.all()
        }

        try:
            response = get_http_request_function()(
                method=service.http_method,
                url=resolved_values["url"],
                headers=headers,
                params=query_params,
                timeout=service.timeout,
                **body_dict,
            )

        except (UnacceptableAddressException, ConnectionError) as e:
            raise UnexpectedDispatchException(
                f"Invalid URL: {resolved_values['url']}"
            ) from e
        except request_exceptions.RequestException as e:
            raise UnexpectedDispatchException(str(e)) from e
        except Exception as e:
            logger.exception("Error while dispatching HTTP request")
            raise UnexpectedDispatchException(f"Unknown error: {str(e)}") from e

        try:
            # Try to parse as JSON regardless of Content-Type. A misconfigured
            # API may return JSON but forget to set the content-type.
            response_body = response.json()
        except request_exceptions.JSONDecodeError:
            # Otherwise, fall back to text
            response_body = response.text

        # Extract the response headers
        response_headers = {key: value for key, value in response.headers.items()}

        data = {
            "raw_body": ensure_string(response_body, allow_empty=True),
            "body": response_body,
            "headers": response_headers,
            "status_code": response.status_code,
        }

        return {"data": data}

    def dispatch_transform(
        self,
        data: Any,
    ) -> DispatchResult:
        return DispatchResult(data=data["data"])


class CoreSMTPEmailServiceType(CoreServiceType):
    type = "smtp_email"
    model_class = CoreSMTPEmailService
    dispatch_types = [DispatchTypes.ACTION]
    integration_type = SMTPIntegrationType.type

    allowed_fields = [
        "integration_id",
        "use_instance_smtp_settings",
        "from_email",
        "from_name",
        "to_emails",
        "cc_emails",
        "bcc_emails",
        "subject",
        "body_type",
        "body",
    ]

    serializer_field_names = [
        "integration_id",
        "use_instance_smtp_settings",
        "instance_smtp_settings_enabled",
        "from_email",
        "from_name",
        "to_emails",
        "cc_emails",
        "bcc_emails",
        "subject",
        "body_type",
        "body",
    ]

    class SerializedDict(ServiceDict):
        use_instance_smtp_settings: bool
        from_email: str
        from_name: str
        to_emails: str
        cc_emails: str
        bcc_emails: str
        subject: str
        body_type: str
        body: str

    simple_formula_fields = [
        "from_email",
        "from_name",
        "to_emails",
        "cc_emails",
        "bcc_emails",
        "subject",
        "body",
    ]

    @property
    def serializer_field_overrides(self):
        from baserow.core.formula.serializers import FormulaSerializerField

        return {
            "use_instance_smtp_settings": serializers.BooleanField(
                required=False,
                default=self._instance_smtp_is_available(),
                help_text=CoreSMTPEmailService._meta.get_field(
                    "use_instance_smtp_settings"
                ).help_text,
            ),
            "integration_id": serializers.IntegerField(
                required=False,
                allow_null=True,
                help_text="The id of the SMTP integration.",
            ),
            "instance_smtp_settings_enabled": serializers.ReadOnlyField(
                help_text="Whether the instance SMTP configuration can be used and should be the default option in the UI.",
            ),
            "from_email": FormulaSerializerField(
                help_text=CoreSMTPEmailService._meta.get_field("from_email").help_text,
            ),
            "from_name": FormulaSerializerField(
                help_text=CoreSMTPEmailService._meta.get_field("from_name").help_text,
            ),
            "to_emails": FormulaSerializerField(
                help_text=CoreSMTPEmailService._meta.get_field("to_emails").help_text,
            ),
            "cc_emails": FormulaSerializerField(
                help_text=CoreSMTPEmailService._meta.get_field("cc_emails").help_text,
            ),
            "bcc_emails": FormulaSerializerField(
                help_text=CoreSMTPEmailService._meta.get_field("bcc_emails").help_text,
            ),
            "subject": FormulaSerializerField(
                help_text=CoreSMTPEmailService._meta.get_field("subject").help_text,
            ),
            "body_type": serializers.ChoiceField(
                choices=[
                    ("plain", "Plain Text"),
                    ("html", "HTML"),
                ],
                help_text=CoreSMTPEmailService._meta.get_field("body_type").help_text,
                required=False,
                default="plain",
            ),
            "body": FormulaSerializerField(
                help_text=CoreSMTPEmailService._meta.get_field("body").help_text,
            ),
        }

    def _instance_smtp_is_available(self) -> bool:
        return bool(
            settings.INTEGRATION_ALLOW_SMTP_SERVICE_TO_USE_INSTANCE_SETTINGS
            and getattr(settings, "EMAIL_HOST", "")
        )

    def _should_use_instance_smtp(self, service: CoreSMTPEmailService) -> bool:
        return bool(
            service.use_instance_smtp_settings and self._instance_smtp_is_available()
        )

    def requires_integration(self, service: CoreSMTPEmailService) -> bool:
        return not self._should_use_instance_smtp(service)

    def prepare_values(self, values, user: AbstractUser, instance=None):
        values = super().prepare_values(values, user, instance)

        use_instance_smtp_settings = (
            values.get(
                "use_instance_smtp_settings",
                instance.use_instance_smtp_settings if instance else True,
            )
            if self._instance_smtp_is_available()
            else False
        )

        if use_instance_smtp_settings:
            values["integration"] = None

        values["use_instance_smtp_settings"] = use_instance_smtp_settings

        return values

    def get_schema_name(self, service: CoreSMTPEmailService) -> str:
        return f"SMTPEmail{service.id}Schema"

    def generate_schema(
        self,
        service: CoreSMTPEmailService,
        allowed_fields: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        properties = {}

        if allowed_fields is None or "success" in allowed_fields:
            properties.update(
                **{
                    "success": {
                        "type": "boolean",
                        "title": "Success",
                        "description": "Whether the email was sent successfully",
                    },
                },
            )

        return {
            "title": self.get_schema_name(service),
            "type": "object",
            "properties": properties,
        }

    def formulas_to_resolve(
        self, service: CoreSMTPEmailService
    ) -> list[FormulaToResolve]:
        """
        Returns the formula to resolve for this service.
        """

        ensurers = {
            "to_emails": lambda v: [ensure_email(e) for e in ensure_array(v)],
            "cc_emails": lambda v: [ensure_email(e) for e in ensure_array(v)],
            "bcc_emails": lambda v: [ensure_email(e) for e in ensure_array(v)],
            "subject": ensure_string,
            "body": ensure_string,
        }

        if not self._should_use_instance_smtp(service):
            ensurers = {
                "from_email": ensure_email,
                "from_name": ensure_string,
                **ensurers,
            }

        formulas = []

        for key, ensurer in ensurers.items():
            formulas.append(
                FormulaToResolve(
                    key, getattr(service, key), ensurer, f'property "{key}"'
                )
            )

        return formulas

    def dispatch_data(
        self,
        service: CoreSMTPEmailService,
        resolved_values: Dict[str, Any],
        dispatch_context: DispatchContext,
    ) -> Any:
        if not resolved_values["to_emails"]:
            raise InvalidContextContentDispatchException(
                "At least one recipient email is required"
            )

        to_emails = resolved_values["to_emails"]
        cc_emails = resolved_values["cc_emails"]
        bcc_emails = resolved_values["bcc_emails"]

        using_instance_smtp = self._should_use_instance_smtp(service)

        if using_instance_smtp:
            from_email = settings.DEFAULT_FROM_EMAIL
            connection = get_connection(
                backend=settings.CELERY_EMAIL_BACKEND,
            )
            smtp_host = settings.EMAIL_HOST
            smtp_port = settings.EMAIL_PORT
        else:
            if not service.integration_id:
                # This situation can happen if we have changed the
                # configuration variable in the meantime.
                raise ServiceImproperlyConfiguredDispatchException(
                    "Integration for this service is missing"
                )

            smtp_integration = service.integration.specific
            from_email = (
                f"{resolved_values['from_name']} <{resolved_values['from_email']}>"
                if resolved_values["from_name"]
                else resolved_values["from_email"]
            )
            connection = get_connection(
                backend="django.core.mail.backends.smtp.EmailBackend",
                host=smtp_integration.host,
                port=smtp_integration.port,
                username=smtp_integration.username,
                password=smtp_integration.password,
                use_tls=smtp_integration.use_tls,
            )
            smtp_host = smtp_integration.host
            smtp_port = smtp_integration.port

        subject = resolved_values["subject"]

        body_content = resolved_values["body"]

        email = EmailMultiAlternatives(
            subject,
            body_content,
            from_email,
            to_emails,
            bcc=bcc_emails,
            cc=cc_emails,
            connection=connection,
        )

        email.content_subtype = service.body_type

        try:
            result = email.send()
            return {
                "data": {
                    "success": result,
                }
            }
        except SMTPNotSupportedError as e:
            raise ServiceImproperlyConfiguredDispatchException(
                "TLS not supported by server"
            ) from e
        except socket.gaierror as e:
            raise ServiceImproperlyConfiguredDispatchException(
                f"The host {smtp_host}:{smtp_port} could not be reached"
            ) from e
        except ConnectionRefusedError as e:
            raise ServiceImproperlyConfiguredDispatchException(
                f"Connection refused by {smtp_host}:{smtp_port}"
            ) from e
        except SMTPAuthenticationError as e:
            raise ServiceImproperlyConfiguredDispatchException(
                "The username or password is incorrect"
            ) from e
        except SMTPConnectError as e:
            raise UnexpectedDispatchException(
                "Unable to connect to the SMTP server"
            ) from e
        except Exception as e:
            raise UnexpectedDispatchException(f"Failed to send email: {str(e)}") from e

    def dispatch_transform(
        self,
        data: Any,
    ) -> DispatchResult:
        return DispatchResult(data=data["data"])

    def export_prepared_values(self, instance: Service) -> dict[str, Any]:
        values = super().export_prepared_values(instance)

        values["integration_id"] = None

        if values.get("integration"):
            del values["integration"]
            values["integration_id"] = instance.integration_id

        return values


class CoreRouterServiceType(CoreServiceType):
    type = "router"
    model_class = CoreRouterService
    allowed_fields = ["default_edge_label"]
    dispatch_types = [DispatchTypes.ACTION]
    serializer_field_names = ["default_edge_label", "edges"]

    class SerializedDict(ServiceDict):
        edges: List[Dict]
        default_edge_label: str

    def enhance_queryset(self, queryset):
        return super().enhance_queryset(queryset).prefetch_related("edges")

    @property
    def serializer_field_overrides(self):
        from baserow.contrib.integrations.api.core.serializers import (
            CoreRouterServiceEdgeSerializer,
        )

        return {
            **super().serializer_field_overrides,
            "edges": CoreRouterServiceEdgeSerializer(
                many=True,
                required=False,
                help_text="The edges associated with this service.",
            ),
        }

    def import_serialized(
        self,
        parent: Any,
        serialized_values: Dict[str, Any],
        id_mapping: Dict[str, Dict[str, str]],
        **kwargs,
    ):
        """
        Responsible for importing the router service and its edges.

        For each edge that we find, generate a new unique ID and store it in the
        `id_mapping` dictionary under the key "automation_edge_outputs".
        """

        for edge in serialized_values["edges"]:
            id_mapping["automation_edge_outputs"][edge["uid"]] = str(uuid.uuid4())

        return super().import_serialized(
            parent,
            serialized_values,
            id_mapping,
            **kwargs,
        )

    def create_instance_from_serialized(
        self,
        serialized_values,
        id_mapping,
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ):
        """
        Responsible for creating the router service and its edges.
        """

        edges = serialized_values.pop("edges", [])
        service = super().create_instance_from_serialized(
            serialized_values,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )
        CoreRouterServiceEdge.objects.bulk_create(
            [
                CoreRouterServiceEdge(
                    service=service,
                    label=edge["label"],
                    condition=edge["condition"],
                    uid=id_mapping["automation_edge_outputs"][edge["uid"]],
                )
                for edge in edges
            ]
        )
        return service

    def serialize_property(
        self,
        service: CoreRouterService,
        prop_name: str,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        """
        Responsible for serializing the `edges` properties.

        :param service: The CoreRouterService service.
        :param prop_name: The property name we're serializing.
        :param files_zip: The zip file containing the files.
        :param storage: The storage to use for the files.
        :param cache: The cache to use for the files.
        """

        if prop_name == "edges":
            return [
                {
                    "label": e.label,
                    "uid": str(e.uid),
                    "condition": e.condition,
                }
                for e in service.edges.all()
            ]

        return super().serialize_property(
            service, prop_name, files_zip=files_zip, storage=storage, cache=cache
        )

    def formulas_to_resolve(self, service: CoreRouterService) -> list[FormulaToResolve]:
        """
        Returns the formula to resolve for this service.
        """

        return [
            FormulaToResolve(
                f"edge_{edge.uid}",
                edge.condition,
                lambda x: ensure_boolean(x, False),
                f'edge "{edge.label}" condition',
            )
            for edge in service.edges.all()
        ]

    def formula_generator(
        self, service: CoreRouterService
    ) -> Generator[str | Instance, str, None]:
        yield from super().formula_generator(service)

        for edge in service.edges.all():
            new_formula = yield edge.condition
            if new_formula is not None:
                edge.condition = new_formula
                yield edge

    def after_update(
        self,
        instance: CoreRouterService,
        values: Dict,
        changes: Dict[str, Tuple],
    ) -> None:
        """
        Responsible for updating router edges which have been PATCHED.

        :param instance: The service we want to manage edges for.
        :param values: A dictionary which may contain edges.
        :param changes: A dictionary containing all changes which were made to the
            service prior to `after_update` being called.
        """

        super().after_update(instance, values, changes)

        if "edges" in values:
            instance.edges.all().delete()
            CoreRouterServiceEdge.objects.bulk_create(
                [
                    CoreRouterServiceEdge(**edge, service=instance, order=index)
                    for index, edge in enumerate(values["edges"])
                ]
            )

    def get_schema_name(self, service: CoreRouterService) -> str:
        return f"CoreRouter{service.id}Schema"

    def export_prepared_values(self, instance: Service) -> dict[str, Any]:
        values = super().export_prepared_values(instance)
        values["edges"] = [
            {
                "label": edge.label,
                "condition": edge.condition,
                "uid": str(edge.uid),
            }
            for edge in instance.edges.all()
        ]
        return values

    def generate_schema(
        self,
        service: CoreRouterService,
        allowed_fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Generates the schema for the router service.

        :param service: The CoreRouterService instance to generate the schema for.
        :param allowed_fields: Optional list of fields to include in the schema.
        :return: A dictionary representing the schema.
        """

        properties = {}
        if allowed_fields is None or "edge" in allowed_fields:
            properties.update(
                **{
                    "edge": {
                        "title": _("Branch taken"),
                        "type": "object",
                        "properties": {
                            "label": {
                                "type": "string",
                                "title": _("Label"),
                                "description": _(
                                    "The label of the "
                                    "branch that matched the condition."
                                ),
                            },
                        },
                    }
                },
            )

        return {
            "title": self.get_schema_name(service),
            "type": "object",
            "properties": properties,
        }

    def dispatch_data(
        self,
        service: CoreRouterService,
        resolved_values: Dict[str, Any],
        dispatch_context: DispatchContext,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Dispatches the router service by evaluating the conditions of its edges
        and returning the first edge that matches the condition.

        If no conditions evaluate to true, it returns the last edge by default, which
        is always false.

        :param service: The CoreRouterService instance to dispatch.
        :param resolved_values: The resolved values from the service's formulas.
        :param dispatch_context: The context in which the service is being dispatched.
        :return: A dictionary containing the data of the first matching edge.
        """

        for edge in service.edges.all():
            condition_result = resolved_values[f"edge_{edge.uid}"]
            if condition_result:
                return {
                    "output_uid": str(edge.uid),
                    "data": {"edge": {"label": edge.label}},
                }

        return {
            "output_uid": "",
            "data": {"edge": {"label": service.default_edge_label}},
        }

    def dispatch_transform(
        self,
        data: Any,
    ) -> DispatchResult:
        return DispatchResult(output_uid=data["output_uid"], data=data["data"])

    def get_sample_data(self, service, dispatch_context):
        """
        If a specific output is forced it means that we need to simulate that
        we traversed this specific output. Let's return the related result.
        """

        if (
            dispatch_context.force_outputs is not None
            and service.id in dispatch_context.force_outputs
        ):
            if dispatch_context.force_outputs[service.id]:
                edge = service.edges.get(uid=dispatch_context.force_outputs[service.id])
                return {
                    "output_uid": str(edge.uid),
                    "data": {"edge": {"label": edge.label}},
                }
            else:
                return {
                    "output_uid": "",
                    "data": {"edge": {"label": service.default_edge_label}},
                }

        return super().get_sample_data(service, dispatch_context)

    def get_edges(self, service):
        return {str(e.uid): {"label": e.label} for e in service.edges.all()} | {
            "": {"label": service.default_edge_label}
        }


class CorePeriodicServiceType(TriggerServiceTypeMixin, CoreServiceType):
    type = "periodic"
    model_class = CorePeriodicService

    allowed_fields = [
        "interval",
        "minute",
        "hour",
        "day_of_week",
        "day_of_month",
    ]

    serializer_field_names = [
        "interval",
        "minute",
        "hour",
        "day_of_week",
        "day_of_month",
        "next_run_at",
    ]

    serializer_field_overrides = {
        "interval": serializers.ChoiceField(
            choices=PERIODIC_INTERVAL_CHOICES,
            help_text=CorePeriodicService._meta.get_field("interval").help_text,
        ),
        "minute": serializers.IntegerField(
            min_value=0,
            max_value=59,
            required=False,
            allow_null=True,
            help_text=CorePeriodicService._meta.get_field("minute").help_text,
        ),
        "hour": serializers.IntegerField(
            min_value=0,
            max_value=23,
            required=False,
            allow_null=True,
            help_text=CorePeriodicService._meta.get_field("hour").help_text,
        ),
        "day_of_week": serializers.IntegerField(
            min_value=0,
            max_value=6,
            required=False,
            allow_null=True,
            help_text=CorePeriodicService._meta.get_field("day_of_week").help_text,
        ),
        "day_of_month": serializers.IntegerField(
            min_value=1,
            max_value=31,
            required=False,
            allow_null=True,
            help_text=CorePeriodicService._meta.get_field("day_of_month").help_text,
        ),
    }

    def __init__(self):
        super().__init__()
        self._cancel_periodic_task = lambda: None

    class SerializedDict(ServiceDict):
        interval: str
        minute: int
        hour: int
        day_of_week: int
        day_of_month: int
        next_run_at: datetime

    def prepare_values(
        self,
        values: Dict[str, Any],
        user: AbstractUser,
        instance: Optional[CorePeriodicService] = None,
    ) -> Dict[str, Any]:
        """
        Responsible for preparing and validating the periodic service values.
        If the `interval` is set to `MINUTE`, it ensures that the `minute` value
        is greater than or equal to the minimum allowed value defined in the settings.

        :param values: The values to prepare.
        :param user: The user creating or updating the service.
        :param instance: The existing service instance, if updating.
        :return: The prepared values.
        """

        minute = values.get("minute", None)
        if values.get("interval") == PERIODIC_INTERVAL_MINUTE and minute is not None:
            if minute < settings.INTEGRATIONS_PERIODIC_MINUTE_MIN:
                raise AutomationNodeMisconfiguredService(
                    "The `minute` value must be greater "
                    f"or equal to {settings.INTEGRATIONS_PERIODIC_MINUTE_MIN}."
                )

        return super().prepare_values(values, user, instance)

    def can_immediately_be_tested(self, service):
        return True

    def _setup_periodic_task(self, sender, **kwargs):
        """
        Responsible for adding the periodic task to call due periodic services.

        :param sender: The sender of the signal.
        """

        from baserow.contrib.integrations.tasks import (
            call_periodic_services_that_are_due,
        )

        sender.add_periodic_task(
            settings.INTEGRATIONS_PERIODIC_TASK_CRONTAB,
            call_periodic_services_that_are_due.s(),
            name="periodic-service-type-task",
        )

        self._cancel_periodic_task = lambda: sender.control.revoke(
            "periodic-service-type-task", terminate=True
        )

    def start_listening(self, on_event: Callable):
        super().start_listening(on_event)
        celery_app.on_after_finalize.connect(self._setup_periodic_task)

    def stop_listening(self):
        super().stop_listening()
        self._cancel_periodic_task()

    def _get_dispatch_payload(self, service: CorePeriodicService) -> Dict[str, str]:
        return {
            "triggered_at": service.last_periodic_run.isoformat(),
            "next_run_at": service.next_run_at.isoformat(),
        }

    def _get_simulation_payload(self, service: CorePeriodicService) -> Dict[str, str]:
        now = timezone.now().replace(second=0, microsecond=0)
        next_run = calculate_next_periodic_run(
            interval=service.interval,
            minute=service.minute,
            hour=service.hour,
            day_of_week=service.day_of_week,
            day_of_month=service.day_of_month,
            from_time=now,
        )
        return {
            "triggered_at": now.isoformat(),
            "next_run_at": next_run.isoformat(),
        }

    def dispatch_data(
        self,
        service: CorePeriodicService,
        resolved_values: Dict[str, Any],
        dispatch_context: DispatchContext,
    ) -> Dict[str, str]:
        """
        Responsible for dispatching a single periodic service. In practice we
        dispatch all periodic services that are due in one go so this method just
        calls `dispatch_all` with a list containing the single service.

        :param service: The CorePeriodicService instance to dispatch.
        :param resolved_values: The resolved values from the service's formulas.
        :param dispatch_context: The context in which the service is being dispatched.
        """

        if dispatch_context.event_payload is not None:
            return dispatch_context.event_payload

        return self._get_simulation_payload(service)

    def get_periodic_services_that_are_due(
        self, current: datetime = None
    ) -> QuerySet[CorePeriodicService]:
        """
        Responsible for fetching all periodic services which are due to be run at the
        given time. It also locks these services to prevent multiple workers from
        dispatching the same service.

        :param current: The current time to compare the `next_run_at` field to.
            If not provided, it will default to the current time.
        :return: A queryset of `CorePeriodicService` instances which are due to be run.
        """

        # If we haven't been given the current time, get it.
        current = current or timezone.now()

        return (
            CorePeriodicService.objects.filter(
                Q(next_run_at__lte=current.replace(second=0, microsecond=0))
                | Q(next_run_at__isnull=True)
            )
            .select_for_update(
                of=("self",),
                skip_locked=True,
            )
            .using(router.db_for_write(CorePeriodicService))
            .order_by("id")
        )

    def call_periodic_services_that_are_due(self):
        """
        Responsible for finding all periodic services that are due. This will likely
        result in services which are due, but not dispatchable, it is up to the parent
        instance (e.g. automation trigger) to determine if the due service is *also*
        dispatchable (e.g. a trigger wants to know if the workflow is published).

        Only services which were dispatched will be included in the bulk-update, where
        the two date fields are refreshed for their next run.
        """

        # Truncate to minute precision for consistent comparisons
        now = timezone.now().replace(second=0, microsecond=0)

        # Determine which services are due to be run. This is not an exhaustive list,
        # it's possible only a subset of these will actually be dispatched.
        periodic_services_due = self.get_periodic_services_that_are_due(now)

        # This list will contain the definitive list of services that were marked
        # for dispatching by the parent, and which we will update the `next_run_at` and
        # `last_periodic_run` fields for.
        periodic_services_dispatched = []

        def _get_service_payload(
            dispatched_service: CorePeriodicService,
        ) -> Dict[str, str]:
            """
            Responsible for returning this service's specific payload,
            and also creating a list of our due services which were *also*
            deemed to be dispatchable by the parent.

            :param dispatched_service: The service which will be dispatched.
            :return: The payload to dispatch for this service.
            """

            # Calculate next run from the current `next_run_at` (not from 'now').
            # This prevents drift even if the service runs late.
            # If the service ran *very* late (e.g. it was scheduled, but the server
            # was down, and we didn't run any services), keep advancing until we get
            # a future time. For example:
            # - A service is scheduled to run every minute.
            #   The next run is scheduled for 10:00:00.
            # - The server is down, and we only restart it at 10:05:00.
            # - When we restart, we run the service (as 10:00:00 <= 10:05:00).
            # - The next run would technically be scheduled for 10:01:00, but that time
            #   is also in the past. So we keep advancing until we find a future time
            #  (10:06:00 in this case).
            next_run = dispatched_service.next_run_at or now
            while next_run <= now:
                next_run = calculate_next_periodic_run(
                    interval=dispatched_service.interval,
                    minute=dispatched_service.minute,
                    hour=dispatched_service.hour,
                    day_of_week=dispatched_service.day_of_week,
                    day_of_month=dispatched_service.day_of_month,
                    from_time=next_run,
                )

            dispatched_service.next_run_at = next_run
            dispatched_service.last_periodic_run = now

            periodic_services_dispatched.append(dispatched_service)
            return self._get_dispatch_payload(dispatched_service)

        self.on_event(
            periodic_services_due,
            _get_service_payload,
        )

        if periodic_services_dispatched:
            CorePeriodicService.objects.bulk_update(
                periodic_services_dispatched, ["next_run_at", "last_periodic_run"]
            )

    def get_schema_name(self, service: CorePeriodicService) -> str:
        return f"Periodic{service.id}Schema"

    def generate_schema(
        self,
        service: CorePeriodicService,
        allowed_fields: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        return {
            "title": self.get_schema_name(service),
            "type": "object",
            "properties": {
                "triggered_at": {
                    "type": "string",
                    "title": _("Previous scheduled run"),
                },
                "next_run_at": {
                    "type": "string",
                    "title": _("Next scheduled run"),
                },
            },
        }


class CoreHTTPTriggerServiceType(TriggerServiceTypeMixin, ServiceType):
    type = "http_trigger"
    model_class = CoreHTTPTriggerService

    allowed_fields = ["uid", "exclude_get", "is_public"]
    serializer_field_names = ["uid", "exclude_get", "is_public"]
    request_serializer_field_names = ["uid", "exclude_get"]

    class SerializedDict(ServiceDict):
        uid: str
        exclude_get: bool
        is_public: bool

    def get_api_urls(self) -> List[path]:
        return [
            path(
                r"webhooks/<uuid:webhook_uid>/",
                CoreHTTPTriggerView.as_view(),
                name="http_trigger",
            ),
        ]

    def serialize_property(
        self,
        service: CoreHTTPTriggerService,
        prop_name: str,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        """
        Responsible for serializing the trigger's properties.

        :param service: The CoreHTTPTriggerService service.
        :param prop_name: The property name we're serializing.
        :param files_zip: The zip file containing the files.
        :param storage: The storage to use for the files.
        :param cache: The cache to use for the files.
        """

        if prop_name == "uid":
            return str(service.uid)

        return super().serialize_property(
            service, prop_name, files_zip=files_zip, storage=storage, cache=cache
        )

    def process_webhook_request(
        self, webhook_uid: uuid.uuid4, request_data: Dict[str, Any], simulate: bool
    ) -> None:
        """
        Finds a CoreHTTPTriggerService instance by its webhook UUID and calls
        the on_event handler to process it.

        :param webhook_uid: The UUID of the service.
        :param request_data: A dict containing the parsed headers, body, etc
            of the webhook request.
        :param simulate: True if the request was for testing the webhook
            service, otherwise False. If False, tries to get the published
            version of the service.
        :raises CoreHTTPTriggerServiceDoesNotExist: When the webhook_uid
            isn't valid.
        :raises CoreHTTPTriggerServiceMethodNotAllowed: When the http
            method isn't allowed for this service.
        """

        # When the service is published, the previous published service may
        # be kept (e.g. see `AutomationWorkflowHandler::publish()`). Since the
        # uid is the same between the two, a filter is necessary to fetch only
        # the latest published service.
        service = (
            self.model_class.objects.filter(uid=webhook_uid, is_public=not simulate)
            .order_by("-id")
            .first()
        )

        if not service:
            raise CoreHTTPTriggerServiceDoesNotExist(uid=webhook_uid)

        if request_data["method"] == "GET" and service.exclude_get:
            raise CoreHTTPTriggerServiceMethodNotAllowed()

        self.on_event([service], request_data)

    def generate_schema(
        self,
        service: CoreHTTPTriggerService,
        allowed_fields: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        properties = {}

        if (allowed_fields is None or "body" in allowed_fields) and service.sample_data:
            schema_builder = SchemaBuilder()
            schema_builder.add_object(
                service.sample_data.get("data", {}).get("body", {})
            )
            schema = schema_builder.to_schema()

            properties |= {
                "body": schema
                | {
                    "title": "Body",
                }
            }

        if allowed_fields is None or "raw_body" in allowed_fields:
            properties |= {
                "raw_body": {
                    "type": "string",
                    "title": "Raw body",
                },
            }

        if (
            allowed_fields is None or "query_params" in allowed_fields
        ) and service.sample_data:
            schema_builder = SchemaBuilder()
            schema_builder.add_object(
                service.sample_data.get("data", {}).get("query_params", {})
            )
            schema = schema_builder.to_schema()

            properties |= {
                "query_params": schema
                | {
                    "title": "Query parameters",
                }
            }

        if allowed_fields is None or "headers" in allowed_fields:
            schema = {}
            if service.sample_data:
                schema_builder = SchemaBuilder()
                schema_builder.add_object(
                    service.sample_data.get("data", {}).get("headers", {})
                )
                schema = schema_builder.to_schema()

            properties.update(
                **{
                    "headers": {
                        "type": "object",
                        "properties": {
                            "Content-Type": {
                                "type": "string",
                                "description": "The MIME type of the request body",
                            },
                            "Content-Length": {
                                "type": "number",
                                "description": "The length of the request body in octets (8-bit bytes)",
                            },
                            "ETag": {
                                "type": "string",
                                "description": "An identifier for a specific version of "
                                "a resource",
                            },
                        },
                        "title": "Headers",
                    }
                    | schema,
                },
            )

        return {
            "title": self.get_schema_name(service),
            "type": "object",
            "properties": properties,
        }

    def import_serialized(
        self,
        parent: Any,
        serialized_values: Dict[str, Any],
        id_mapping: Dict[str, Dict[str, str]],
        import_export_config: Optional[ImportExportConfig] = None,
        **kwargs,
    ):
        """
        Handle the is_public field during import based on publishing context.
        """

        if import_export_config:
            if import_export_config.is_publishing:
                serialized_values["is_public"] = True
            if import_export_config.is_duplicate:
                # Ensure that duplicating a service (e.g. installing a template)
                # results in a new unique uuid.
                serialized_values["uid"] = str(uuid.uuid4())

        return super().import_serialized(
            parent,
            serialized_values,
            id_mapping,
            import_export_config=import_export_config,
            **kwargs,
        )

    def export_prepared_values(
        self, instance: CoreHTTPTriggerService
    ) -> dict[str, Any]:
        values = super().export_prepared_values(instance)

        values["uid"] = str(values["uid"])

        return values


class CoreIteratorServiceType(ListServiceTypeMixin, ServiceType):
    type = "iterator"
    model_class = CoreIteratorService
    dispatch_types = DispatchTypes.ACTION

    allowed_fields = [
        "source",
    ]

    serializer_field_names = [
        "source",
    ]

    class SerializedDict(ServiceDict):
        source: str

    simple_formula_fields = [
        "source",
    ]

    @property
    def serializer_field_overrides(self):
        from baserow.core.formula.serializers import FormulaSerializerField

        return {
            "source": FormulaSerializerField(
                help_text=CoreIteratorService._meta.get_field("source").help_text,
                required=False,
            ),
        }

    def get_schema_name(self, service: CoreSMTPEmailService) -> str:
        return f"Iterator{service.id}Schema"

    def generate_schema(
        self,
        service: CoreIteratorService,
        allowed_fields: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        if service.sample_data and (
            allowed_fields is None or "items" in allowed_fields
        ):
            schema_builder = SchemaBuilder()
            schema_builder.add_object(service.sample_data["data"]["results"])
            schema = schema_builder.to_schema()

            # Sometimes there is no items if the array is empty
            if "items" in schema:
                return {
                    **schema,
                    "title": self.get_schema_name(service),
                }
            else:
                return None
        else:
            return None

    def formulas_to_resolve(self, service: CoreRouterService) -> list[FormulaToResolve]:
        """
        Returns the formula to resolve for this service.
        """

        return [
            FormulaToResolve(
                "source",
                service.source,
                ensure_array,
                "'source' property",
            )
        ]

    def dispatch_data(
        self,
        service: CoreSMTPEmailService,
        resolved_values: Dict[str, Any],
        dispatch_context: DispatchContext,
    ) -> Any:
        return {"results": resolved_values["source"], "has_next_page": False}

    def dispatch_transform(
        self,
        data: Any,
    ) -> DispatchResult:
        return DispatchResult(data=data)
