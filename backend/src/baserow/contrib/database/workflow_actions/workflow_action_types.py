from typing import TYPE_CHECKING, Any, Dict, Generator, List, Optional
from zipfile import ZipFile

from django.contrib.auth.models import AbstractUser
from django.core.files.storage import Storage
from django.db.models import Manager, Prefetch, QuerySet

from rest_framework import serializers
from rest_framework.exceptions import ErrorDetail
from rest_framework.fields import empty

from baserow.api.services.serializers import PolymorphicServiceRequestSerializer
from baserow.contrib.database.api.workflow_actions.serializers import (
    DatabasePolymorphicServiceSerializer,
)
from baserow.contrib.database.workflow_actions.models import (
    CoreHTTPRequestWorkflowAction,
    CoreSMTPEmailWorkflowAction,
    LocalBaserowCreateRowWorkflowAction,
    LocalBaserowDeleteRowWorkflowAction,
    LocalBaserowUpdateRowWorkflowAction,
    OpenUrlWorkflowAction,
)
from baserow.contrib.database.workflow_actions.registries import (
    DatabaseWorkflowActionType,
)
from baserow.contrib.database.workflow_actions.types import DatabaseWorkflowActionDict
from baserow.contrib.integrations.core.service_types import (
    CoreHTTPRequestServiceType,
    CoreSMTPEmailServiceType,
)
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowDeleteRowServiceType,
    LocalBaserowUpsertRowServiceType,
)
from baserow.core.db import specific_queryset
from baserow.core.formula.serializers import FormulaSerializerField
from baserow.core.registry import Instance
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.models import Service
from baserow.core.services.registries import service_type_registry
from baserow.core.services.types import DispatchResult
from baserow.core.workflow_actions.models import WorkflowAction

if TYPE_CHECKING:
    from baserow.contrib.database.workflow_actions.dispatch_context import (
        DatabaseDispatchContext,
    )


class DefaultTypedServiceRequestSerializer(PolymorphicServiceRequestSerializer):
    """
    A service request serializer that names the service type itself when the
    caller leaves it out, so an action can be created already configured.

    The action type decides which service backs it, and the editor knows that
    service under a name of its own, so it has no way to supply this one.
    """

    def __init__(self, *args, service_type_name: str = None, **kwargs):
        self.service_type_name = service_type_name
        super().__init__(*args, **kwargs)

    def run_validation(self, data=empty) -> Any:
        if isinstance(data, dict):
            supplied_type = data.get("type")
            if not supplied_type:
                data = {**data, "type": self.service_type_name}
            elif supplied_type != self.service_type_name:
                # The action type already fixes which service backs it, so a
                # different type here only picks the serializer, and whatever
                # it accepted is then dropped without a word. Refused rather
                # than corrected, so the caller hears about it.
                raise serializers.ValidationError(
                    {
                        "type": [
                            ErrorDetail(
                                f"This action is always backed by a "
                                f"'{self.service_type_name}' service, so "
                                f"'{supplied_type}' cannot be used here.",
                                code="invalid",
                            )
                        ]
                    }
                )
        return super().run_validation(data)


class DatabaseWorkflowServiceActionType(DatabaseWorkflowActionType):
    service_type = None  # Must be implemented by subclasses.

    # Service values that shape the answer a click remembers. Changing one
    # makes an earlier capture describe a request no longer being made, so it
    # is dropped. Only read by a type that sets `captures_sample_data`.
    sample_data_shaping_fields: List[str] = []

    serializer_field_names = ["service"]
    serializer_field_overrides = {
        "service": DatabasePolymorphicServiceSerializer(
            help_text="The service which this workflow action is associated with."
        )
    }
    request_serializer_field_names = ["service"]

    class SerializedDict(DatabaseWorkflowActionDict):
        service: Dict

    def get_field_overrides(
        self, request_serializer: bool, extra_params: Dict, **kwargs
    ) -> Dict:
        # Built per type rather than declared, so the serializer can fall back
        # to the service type this action carries.
        if request_serializer:
            return {
                "service": DefaultTypedServiceRequestSerializer(
                    service_type_name=self.service_type,
                    default=None,
                    required=False,
                    help_text="The service which this workflow action is "
                    "associated with.",
                )
            }

        return super().get_field_overrides(request_serializer, extra_params, **kwargs)

    @property
    def allowed_fields(self) -> List[str]:
        return super().allowed_fields + ["service"]

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, Any]:
        service_type = service_type_registry.get(self.service_type)
        return {"service": pytest_data_fixture.create_service(service_type.model_class)}

    def get_pytest_params_serialized(
        self, pytest_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        service_type = service_type_registry.get_by_model(pytest_params["service"])
        return {"service": service_type.export_serialized(pytest_params["service"])}

    def export_serialized(
        self,
        instance: WorkflowAction,
        import_export_config: Optional[Any] = None,
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Blanks whatever the backing service calls sensitive. `serialize_property`
        is where the service is exported, and it is never handed the config, so
        the stripping happens here instead.

        A key on an HTTP action lives in the service's own headers rather than
        in an integration, so without this it travels with every export.
        """

        exported = super().export_serialized(
            instance, import_export_config, files_zip, storage, cache
        )

        if getattr(import_export_config, "exclude_sensitive_data", False):
            service = exported.get("service") or {}
            for prop_name in instance.service.specific.get_type().sensitive_fields:
                if prop_name not in service:
                    continue
                rows = service[prop_name]
                if isinstance(rows, list):
                    # Only the value is dropped. Blanking the whole list would
                    # take `Content-Type` and `api-version` with the key, and
                    # the imported button would send a different request while
                    # looking configured. Keeping the names says what has to be
                    # entered again, which is what the data sync types do.
                    service[prop_name] = [
                        {**row, "value": None} if isinstance(row, dict) else row
                        for row in rows
                    ]
                else:
                    service[prop_name] = None

        return exported

    def serialize_property(
        self,
        workflow_action: WorkflowAction,
        prop_name: str,
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict[str, Any]] = None,
    ) -> Any:
        if prop_name == "service":
            service = workflow_action.service.specific
            exported = service.get_type().export_serialized(
                service, files_zip=files_zip, storage=storage, cache=cache
            )
            # An export travels to snapshots, copies and templates, and what a
            # click remembered describes this installation's data. Nothing
            # needs it there: the editor rebuilds it from the next click.
            exported.pop("sample_data", None)
            return exported

        return super().serialize_property(
            workflow_action,
            prop_name,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )

    def deserialize_property(
        self,
        prop_name: str,
        value: Any,
        id_mapping: Dict[str, Dict[int, int]],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Any:
        """
        Recreates the backing service from its serialized values. The service
        type remaps its own references, such as the target table id.
        """

        if prop_name == "service" and value:
            return ServiceHandler().import_service(
                # Database services carry no integration; the acting user comes
                # from the dispatch context instead.
                None,
                value,
                id_mapping,
                storage=storage,
                cache=cache,
                files_zip=files_zip,
                import_export_config=kwargs.get("import_export_config"),
            )

        return super().deserialize_property(
            prop_name,
            value,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

    def prepare_values(
        self,
        values: Dict[str, Any],
        user: AbstractUser,
        instance: Optional[WorkflowAction] = None,
    ) -> Dict[str, Any]:
        """
        Creates the backing service when the action is new, and forwards any
        supplied service values to it.
        """

        service_type = service_type_registry.get(self.service_type)

        if not instance:
            service = ServiceHandler().create_service(service_type)
        else:
            service = instance.service.specific

        service_values = values.pop("service", None) or {}
        # Security, not tidiness: `integration_id` is writable and looked up
        # without a permission check, and an integration's `authorized_user`
        # outranks the actor, so a caller could make every click run as someone
        # else. Database services carry no integration (ADR 006 section 5).
        service_values.pop("integration_id", None)
        prepared_service_values = service_type.prepare_values(
            service_values, user, service if instance else None
        )
        if instance and self._reshapes_the_request(service, prepared_service_values):
            # Saved by `update_service` below, in the same write.
            service.sample_data = None
        ServiceHandler().update_service(
            service_type, service, **prepared_service_values
        )

        values["service"] = service
        return super().prepare_values(values, user, instance)

    def _reshapes_the_request(
        self, service: Service, prepared_service_values: Dict[str, Any]
    ) -> bool:
        """
        Whether this update changes what the answer will look like, which is
        what makes an earlier capture stale. Read before the update, while the
        service still holds the values it is replacing.

        :param service: The service as it is stored right now.
        :param prepared_service_values: What the update is about to set. A
            value the caller left out is not compared: it is not changing.
        :return: True when a captured answer no longer describes this request.
        """

        if not self.captures_sample_data or not service.sample_data:
            return False

        for name in self.sample_data_shaping_fields:
            if name not in prepared_service_values:
                continue

            stored = getattr(service, name)
            supplied = prepared_service_values[name]

            if isinstance(stored, Manager):
                # A related row, such as a header or a query parameter.
                stored = [{"key": row.key, "value": row.value} for row in stored.all()]
                supplied = [
                    {"key": row["key"], "value": row["value"]} for row in supplied or []
                ]

            if stored != supplied:
                return True

        return False

    def formula_generator(
        self, workflow_action: WorkflowAction
    ) -> Generator[str | Instance, str, None]:
        yield from super().formula_generator(workflow_action)

        service = workflow_action.service.specific
        yield from service.get_type().formula_generator(service)

    def enhance_queryset(self, queryset: QuerySet) -> QuerySet:
        return (
            super()
            .enhance_queryset(queryset)
            .prefetch_related(
                Prefetch(
                    "service",
                    queryset=specific_queryset(
                        Service.objects.all(),
                        per_content_type_queryset_hook=(
                            lambda service,
                            queryset: service_type_registry.get_by_model(
                                service
                            ).enhance_queryset(queryset)
                        ),
                    ),
                )
            )
        )

    def get_result_field_names(self, workflow_action: WorkflowAction) -> Dict[str, str]:
        service = workflow_action.service.specific
        service_type = service.get_type()
        get_field_objects = getattr(service_type, "get_table_field_objects", None)
        if get_field_objects is None:
            return {}
        return {
            field_object["field"].db_column: field_object["field"].name
            for field_object in get_field_objects(service) or []
        }

    def dispatch(
        self,
        workflow_action: WorkflowAction,
        dispatch_context: "DatabaseDispatchContext",
    ) -> DispatchResult:
        service = workflow_action.service.specific
        # A database service runs as the dispatch actor, never as an
        # integration's `authorized_user` (ADR 006 section 5).
        if service.integration_id is not None:
            raise ServiceImproperlyConfiguredDispatchException(
                "A database service cannot use an integration."
            )
        return ServiceHandler().dispatch_service(service, dispatch_context)


class LocalBaserowCreateRowWorkflowActionType(DatabaseWorkflowServiceActionType):
    type = "local_baserow_create_row"
    model_class = LocalBaserowCreateRowWorkflowAction
    service_type = LocalBaserowUpsertRowServiceType.type


class LocalBaserowUpdateRowWorkflowActionType(DatabaseWorkflowServiceActionType):
    type = "local_baserow_update_row"
    model_class = LocalBaserowUpdateRowWorkflowAction
    service_type = LocalBaserowUpsertRowServiceType.type


class LocalBaserowDeleteRowWorkflowActionType(DatabaseWorkflowServiceActionType):
    type = "local_baserow_delete_row"
    model_class = LocalBaserowDeleteRowWorkflowAction
    service_type = LocalBaserowDeleteRowServiceType.type


class CoreHTTPRequestWorkflowActionType(DatabaseWorkflowServiceActionType):
    type = "http_request"
    model_class = CoreHTTPRequestWorkflowAction
    service_type = CoreHTTPRequestServiceType.type

    # What an endpoint answers with is unknowable until it has answered once.
    captures_sample_data = True
    is_external = True

    # Everything that decides which request goes out. `timeout` is left out:
    # it changes how long the answer may take, not what is in it.
    sample_data_shaping_fields = [
        "http_method",
        "url",
        "body_type",
        "body_content",
        "headers",
        "query_params",
        "form_data",
    ]

    def unusable_result_reason(self, result: DispatchResult) -> Optional[str]:
        data = result.data if isinstance(result.data, dict) else {}
        status_code = data.get("status_code")

        if isinstance(status_code, int) and 200 <= status_code < 300:
            return None

        # An error page describes the failure, not the endpoint, and would
        # replace the shape a working click learned. The status code says
        # nothing about the address, so it is safe to repeat.
        if status_code == 504:
            return "The last click timed out before the endpoint answered."
        if isinstance(status_code, int):
            return (
                f"The last click was answered with {status_code}, which "
                f"describes the failure rather than the endpoint."
            )
        return "The last click was not answered with anything describable."


class CoreSMTPEmailWorkflowActionType(DatabaseWorkflowServiceActionType):
    type = "smtp_email"
    model_class = CoreSMTPEmailWorkflowAction
    service_type = CoreSMTPEmailServiceType.type
    is_external = True

    def prepare_values(self, values, user, instance=None):
        """
        A database action carries no integration (ADR 006 section 5), so the
        instance server is the only thing it can send through. Pinned here
        rather than in the form, or an API client could store an action that
        can never send.
        """

        values = super().prepare_values(values, user, instance)
        service = values["service"]
        if not service.use_instance_smtp_settings:
            service.use_instance_smtp_settings = True
            service.save(update_fields=["use_instance_smtp_settings"])
        return values

    # What each reason the service gives means for a button, in the words the
    # API answers a refusal with.
    DEACTIVATED_REASONS = {
        CoreSMTPEmailServiceType.INSTANCE_SMTP_TURNED_OFF: (
            "Sending through this Baserow instance's own SMTP server is turned "
            "off, so a button cannot send email."
        ),
        CoreSMTPEmailServiceType.INSTANCE_SMTP_NO_SERVER: (
            "This Baserow instance has no SMTP server configured, so a button "
            "cannot send email."
        ),
    }

    def is_deactivated(self, workspace) -> bool:
        """
        A database action carries no integration, so the instance SMTP server
        is the only way it can send. Without one, refuse it up front rather
        than failing on every click.

        :param workspace: The workspace the button field belongs to.
        :return: True when this installation cannot send at all.
        """

        service_type = service_type_registry.get(self.service_type)
        return not service_type.instance_smtp_is_available()

    def get_deactivated_reason(self, workspace) -> Optional[str]:
        """
        Which of the two ways to be unable to send this installation is in.

        :param workspace: The workspace the button field belongs to.
        :return: The reason in words, or `None` when it can send.
        """

        service_type = service_type_registry.get(self.service_type)
        reason = service_type.instance_smtp_unavailable_reason()
        return self.DEACTIVATED_REASONS.get(reason)


class OpenUrlWorkflowActionType(DatabaseWorkflowActionType):
    type = "open_url"
    model_class = OpenUrlWorkflowAction
    is_frontend_only = True

    allowed_fields = DatabaseWorkflowActionType.allowed_fields + ["url", "target"]
    serializer_field_names = ["url", "target"]
    # Remapped on import by the deferred pass in `DatabaseWorkflowActionType`.
    simple_formula_fields = ["url"]
    serializer_field_overrides = {
        "url": FormulaSerializerField(
            help_text="The URL to open, as a formula.",
            required=False,
        ),
    }

    class SerializedDict(DatabaseWorkflowActionDict):
        url: str
        target: str
