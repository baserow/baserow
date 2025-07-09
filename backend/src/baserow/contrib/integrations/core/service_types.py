import json
import socket
from smtplib import SMTPAuthenticationError, SMTPConnectError, SMTPNotSupportedError
from typing import Any, Dict, Generator, List, Optional, Tuple

from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives, get_connection

import advocate
from loguru import logger
from requests import exceptions as request_exceptions
from rest_framework import serializers

from baserow.contrib.integrations.core.models import (
    CoreHTTPRequestService,
    CoreSMTPEmailService,
    HTTPFormData,
    HTTPHeader,
    HTTPQueryParam,
)
from baserow.core.formula import resolve_formula
from baserow.core.formula.exceptions import (
    BaserowFormulaException,
    InvalidFormulaContext,
    InvalidFormulaContextContent,
)
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.formula.validator import ensure_array, ensure_email, ensure_string
from baserow.core.registry import Instance
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.exceptions import (
    InvalidContextContentDispatchException,
    InvalidContextDispatchException,
    ServiceImproperlyConfiguredDispatchException,
    UnexpectedDispatchException,
)
from baserow.core.services.models import Service
from baserow.core.services.registries import DispatchTypes, ServiceType
from baserow.core.services.types import DispatchResult, ServiceDict
from baserow.version import VERSION as BASEROW_VERSION

from .constants import BODY_TYPE, HTTP_METHOD
from .integration_types import SMTPIntegrationType


class CoreHTTPRequestServiceType(ServiceType):
    type = "http_request"
    model_class = CoreHTTPRequestService
    dispatch_type = DispatchTypes.DISPATCH_WORKFLOW_ACTION

    allowed_fields = [
        "http_method",
        "url",
        "body_type",
        "body_content",
        "timeout",
    ]

    serializer_field_names = [
        "http_method",
        "url",
        "headers",
        "query_params",
        "form_data",
        "body_type",
        "body_content",
        "timeout",
        "response_sample",
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
        response_sample: dict

    simple_formula_fields = ["body_content", "url"]

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
                allow_blank=True,
                required=False,
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
                allow_blank=True,
                required=False,
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
            new_formula = yield fdata.value
            if new_formula is not None:
                fdata.value = new_formula
                yield fdata

        # Return headers formulas
        for header in service.headers.all():
            new_formula = yield header.value
            if new_formula is not None:
                header.value = new_formula
                yield header

        # Return headers formulas
        for query_param in service.query_params.all():
            new_formula = yield query_param.value
            if new_formula is not None:
                query_param.value = new_formula
                yield query_param

    def extract_properties(self, path: List[str], **kwargs) -> List[str]:
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

        if allowed_fields is None or "raw_body" in allowed_fields:
            properties.update(
                **{
                    "raw_body": {
                        "type": "string",
                        "title": "Body",
                    },
                },
            )

        if allowed_fields is None or "headers" in allowed_fields:
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
                    },
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

    def resolve_service_formulas(
        self,
        service: CoreHTTPRequestService,
        dispatch_context: DispatchContext,
    ) -> Dict[str, Any]:
        """
        Resolves the formulas for url, body, form_data, headers and query_params.
        """

        resolved_values = {}

        resolved_values["body_content"] = ensure_string(
            resolve_formula(
                service.body_content,
                formula_runtime_function_registry,
                dispatch_context,
            )
        )

        dispatch_context.reset_call_stack()
        resolved_values["url"] = ensure_string(
            resolve_formula(
                service.url,
                formula_runtime_function_registry,
                dispatch_context,
            )
        )

        for fdata in service.form_data.all():
            dispatch_context.reset_call_stack()
            try:
                resolved_values[f"form_data_{fdata.id}"] = ensure_string(
                    resolve_formula(
                        fdata.value,
                        formula_runtime_function_registry,
                        dispatch_context,
                    )
                )
            except InvalidFormulaContext as e:
                raise InvalidContextDispatchException(str(e)) from e
            except InvalidFormulaContextContent as e:
                message = f'Value error for form data "{fdata.key}": {str(e)}'
                raise InvalidContextContentDispatchException(message) from e
            except BaserowFormulaException as e:
                message = f'Error in formula for form data "{fdata.key}": {str(e)}'
                raise ServiceImproperlyConfiguredDispatchException(message) from e
            except ServiceImproperlyConfiguredDispatchException:
                raise
            except Exception as e:
                logger.exception(f"Unexpected error for form data {fdata.key}")
                message = (
                    "Unknown error in formula for "
                    f"form_data {fdata.key}: {repr(e)} - {str(e)}"
                )
                raise UnexpectedDispatchException(message) from e

        for header in service.headers.all():
            dispatch_context.reset_call_stack()
            try:
                resolved_values[f"header_{header.id}"] = ensure_string(
                    resolve_formula(
                        header.value,
                        formula_runtime_function_registry,
                        dispatch_context,
                    )
                )
            except InvalidFormulaContext as e:
                raise InvalidContextDispatchException(str(e)) from e
            except InvalidFormulaContextContent as e:
                message = f'Value error for header "{header.key}": {str(e)}'
                raise InvalidContextContentDispatchException(message) from e
            except BaserowFormulaException as e:
                message = f'Error in formula for header "{header.key}": {str(e)}'
                raise ServiceImproperlyConfiguredDispatchException(message) from e
            except ServiceImproperlyConfiguredDispatchException:
                raise
            except Exception as e:
                logger.exception(f'Unexpected error for header "{header.key}"')
                message = (
                    "Unknown error in formula for "
                    f'header "{header.key}": {repr(e)} - {str(e)}'
                )
                raise UnexpectedDispatchException(message) from e

        for param in service.query_params.all():
            dispatch_context.reset_call_stack()
            try:
                resolved_values[f"param_{param.id}"] = ensure_string(
                    resolve_formula(
                        param.value,
                        formula_runtime_function_registry,
                        dispatch_context,
                    )
                )
            except InvalidFormulaContext as e:
                raise InvalidContextDispatchException(str(e)) from e
            except InvalidFormulaContextContent as e:
                message = f'Value error for query param "{param.key}": {str(e)}'
                raise InvalidContextContentDispatchException(message) from e
            except BaserowFormulaException as e:
                message = f'Error in formula for query param "{param.key}": {str(e)}'
                raise ServiceImproperlyConfiguredDispatchException(message) from e
            except ServiceImproperlyConfiguredDispatchException:
                raise
            except Exception as e:
                logger.exception(f'Unexpected error for query param "{param.key}"')
                message = (
                    "Unknown error in formula for "
                    f'query param "{param.key}": {repr(e)} - {str(e)}'
                )
                raise UnexpectedDispatchException(message) from e

        return resolved_values

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
            response = advocate.request(
                method=service.http_method,
                url=resolved_values["url"],
                headers=headers,
                params=query_params,
                timeout=service.timeout,
                **body_dict,
            )
        except request_exceptions.RequestException as e:
            raise UnexpectedDispatchException(str(e)) from e
        except Exception as e:
            raise UnexpectedDispatchException(f"Unknown error: {str(e)}") from e

        response_body = (
            response.json()
            if response.headers.get("Content-Type") == "application/json"
            else response.text
        )

        # Extract the response headers
        response_headers = {key: value for key, value in response.headers.items()}

        return {
            "data": {
                # For now we always convert the body to a string
                "raw_body": ensure_string(response_body, allow_empty=True),
                "headers": response_headers,
                "status_code": response.status_code,
            },
        }

    def dispatch_transform(
        self,
        data: Any,
    ) -> DispatchResult:
        return DispatchResult(data=data["data"])


class CoreSMTPEmailServiceType(ServiceType):
    type = "smtp_email"
    model_class = CoreSMTPEmailService
    dispatch_type = DispatchTypes.DISPATCH_WORKFLOW_ACTION
    integration_type = SMTPIntegrationType.type

    allowed_fields = [
        "integration_id",
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
        from_email: str
        from_name: str
        to_emails: str
        cc_emails: str
        bcc_emails: str
        subject: str
        body_type: str
        body: str
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
            "integration_id": serializers.IntegerField(
                required=False,
                allow_null=True,
                help_text="The id of the SMTP integration.",
            ),
            "from_email": FormulaSerializerField(
                help_text=CoreSMTPEmailService._meta.get_field("from_email").help_text,
                allow_blank=True,
                required=False,
                default="",
            ),
            "from_name": FormulaSerializerField(
                help_text=CoreSMTPEmailService._meta.get_field("from_name").help_text,
                allow_blank=True,
                required=False,
                default="",
            ),
            "to_emails": FormulaSerializerField(
                help_text=CoreSMTPEmailService._meta.get_field("to_emails").help_text,
                allow_blank=True,
                required=False,
                default="",
            ),
            "cc_emails": FormulaSerializerField(
                help_text=CoreSMTPEmailService._meta.get_field("cc_emails").help_text,
                allow_blank=True,
                required=False,
                default="",
            ),
            "bcc_emails": FormulaSerializerField(
                help_text=CoreSMTPEmailService._meta.get_field("bcc_emails").help_text,
                allow_blank=True,
                required=False,
                default="",
            ),
            "subject": FormulaSerializerField(
                help_text=CoreSMTPEmailService._meta.get_field("subject").help_text,
                allow_blank=True,
                required=False,
                default="",
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
                allow_blank=True,
                required=False,
                default="",
            ),
        }

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

    def resolve_service_formulas(
        self,
        service: CoreSMTPEmailService,
        dispatch_context: DispatchContext,
    ) -> Dict[str, Any]:
        resolved_values = {}

        ensurers = {
            "from_email": ensure_email,
            "from_name": ensure_string,
            "to_emails": lambda v: [ensure_email(e) for e in ensure_array(v)],
            "cc_emails": lambda v: [ensure_email(e) for e in ensure_array(v)],
            "bcc_emails": lambda v: [ensure_email(e) for e in ensure_array(v)],
            "subject": ensure_string,
            "body": ensure_string,
        }

        for field_name, ensurer in ensurers.items():
            dispatch_context.reset_call_stack()
            field_value = getattr(service, field_name)
            try:
                resolved_values[field_name] = ensurer(
                    resolve_formula(
                        field_value,
                        formula_runtime_function_registry,
                        dispatch_context,
                    )
                )
            except InvalidFormulaContext as e:
                raise InvalidContextDispatchException(str(e)) from e
            except (InvalidFormulaContextContent, ValidationError) as e:
                message = f'Value error for property "{field_name}": {str(e)}'
                raise InvalidContextContentDispatchException(message) from e
            except BaserowFormulaException as e:
                message = f'Error in formula for property "{field_name}": {str(e)}'
                raise ServiceImproperlyConfiguredDispatchException(message) from e
            except Exception as e:
                logger.exception(f'Unexpected error for property "{field_name}"')
                message = (
                    f'Unknown error in formula for property "{field_name}": {str(e)}'
                )
                raise UnexpectedDispatchException(message) from e

        if not resolved_values["to_emails"]:
            raise InvalidContextContentDispatchException(
                "At least one recipient email is required"
            )

        return resolved_values

    def dispatch_data(
        self,
        service: CoreSMTPEmailService,
        resolved_values: Dict[str, Any],
        dispatch_context: DispatchContext,
    ) -> Any:
        if not service.integration:
            raise ServiceImproperlyConfiguredDispatchException(
                "SMTP Email service must be connected to an SMTP integration"
            )

        smtp_integration = service.integration.specific

        to_emails = resolved_values["to_emails"]
        cc_emails = resolved_values["cc_emails"]
        bcc_emails = resolved_values["bcc_emails"]

        from_email = (
            f"{resolved_values['from_name']} <{resolved_values['from_email']}>"
            if resolved_values["from_name"]
            else resolved_values["from_email"]
        )

        subject = resolved_values["subject"]

        body_content = resolved_values["body"]

        connection = get_connection(
            backend="django.core.mail.backends.smtp.EmailBackend",
            host=smtp_integration.host,
            port=smtp_integration.port,
            username=smtp_integration.username,
            password=smtp_integration.password,
            use_tls=smtp_integration.use_tls,
        )

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
                f"The host {smtp_integration.host}:{smtp_integration.port} could not "
                "be reached"
            ) from e
        except ConnectionRefusedError as e:
            raise ServiceImproperlyConfiguredDispatchException(
                f"Connection refused by {smtp_integration.host}:{smtp_integration.port}"
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

    def export_prepared_values(self, instance: Service) -> dict[str, any]:
        values = super().export_prepared_values(instance)
        if values.get("integration"):
            del values["integration"]
            values["integration_id"] = instance.integration_id
        return values
