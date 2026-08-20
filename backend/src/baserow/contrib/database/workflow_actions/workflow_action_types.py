from typing import TYPE_CHECKING, Any, Dict, Generator, List, Optional
from zipfile import ZipFile

from django.contrib.auth.models import AbstractUser
from django.core.files.storage import Storage
from django.db.models import Prefetch, QuerySet

from rest_framework.fields import empty

from baserow.api.services.serializers import PolymorphicServiceRequestSerializer
from baserow.contrib.database.api.workflow_actions.serializers import (
    DatabasePolymorphicServiceSerializer,
)
from baserow.contrib.database.workflow_actions.models import (
    LocalBaserowCreateRowWorkflowAction,
    LocalBaserowDeleteRowWorkflowAction,
    LocalBaserowUpdateRowWorkflowAction,
    OpenUrlWorkflowAction,
)
from baserow.contrib.database.workflow_actions.registries import (
    DatabaseWorkflowActionType,
)
from baserow.contrib.database.workflow_actions.types import DatabaseWorkflowActionDict
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
        if isinstance(data, dict) and not data.get("type"):
            data = {**data, "type": self.service_type_name}
        return super().run_validation(data)


class DatabaseWorkflowServiceActionType(DatabaseWorkflowActionType):
    service_type = None  # Must be implemented by subclasses.

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
            return service.get_type().export_serialized(
                service, files_zip=files_zip, storage=storage, cache=cache
            )

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
        ServiceHandler().update_service(
            service_type, service, **prepared_service_values
        )

        values["service"] = service
        return super().prepare_values(values, user, instance)

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
