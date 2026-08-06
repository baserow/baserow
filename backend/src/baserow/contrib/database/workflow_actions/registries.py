from typing import TYPE_CHECKING, Any, Dict, Generator

from django.contrib.auth.models import AbstractUser
from django.db.models import Prefetch

from baserow.api.services.serializers import (
    PolymorphicServiceRequestSerializer,
    PolymorphicServiceSerializer,
)
from baserow.contrib.database.formula_importer import import_formula
from baserow.contrib.database.workflow_actions.types import DatabaseWorkflowActionDict
from baserow.core.db import specific_queryset
from baserow.core.deferred_callbacks import register_deferred_callback
from baserow.core.registry import (
    CustomFieldsInstanceMixin,
    CustomFieldsRegistryMixin,
    Instance,
    ModelRegistryMixin,
    Registry,
)
from baserow.core.services.exceptions import InvalidServiceTypeDispatchSource
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.models import Service
from baserow.core.services.registries import service_type_registry
from baserow.core.services.types import DispatchResult
from baserow.core.workflow_actions.models import WorkflowAction
from baserow.core.workflow_actions.registries import WorkflowActionType

if TYPE_CHECKING:
    from baserow.contrib.database.workflow_actions.dispatch_context import (
        DatabaseDispatchContext,
    )


class DatabaseWorkflowActionType(WorkflowActionType, CustomFieldsInstanceMixin):
    allowed_fields = ["order", "field", "field_id"]
    parent_property_name = "field"
    id_mapping_name = "database_workflow_actions"

    # Frontend-only types are never dispatched server side. The dispatch
    # service skips them and returns them to the browser to execute.
    is_frontend_only = False

    class SerializedDict(DatabaseWorkflowActionDict):
        pass

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, Any]:
        return {}

    def dispatch(self, workflow_action, dispatch_context):
        raise InvalidServiceTypeDispatchSource(
            "This workflow action type cannot be dispatched."
        )


class DatabaseWorkflowServiceActionType(DatabaseWorkflowActionType):
    service_type = None  # Must be implemented by subclasses.

    serializer_field_names = ["service"]
    serializer_field_overrides = {
        "service": PolymorphicServiceSerializer(
            help_text="The service which this workflow action is associated with."
        )
    }
    request_serializer_field_names = ["service"]
    request_serializer_field_overrides = {
        "service": PolymorphicServiceRequestSerializer(
            default=None,
            required=False,
            help_text="The service which this workflow action is associated with.",
        )
    }

    class SerializedDict(DatabaseWorkflowActionDict):
        service: Dict

    @property
    def allowed_fields(self):
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
        self, workflow_action, prop_name, files_zip=None, storage=None, cache=None
    ):
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
        prop_name,
        value,
        id_mapping,
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ):
        """
        Recreates the backing service from its serialized values. The service
        type remaps its own references, such as the target table id.
        """

        if prop_name == "service" and value:
            return ServiceHandler().import_service(
                # Database services are never tied to an integration, see the
                # integration-less dispatch path added in phase 2a.
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
        instance: WorkflowAction = None,
    ):
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
        # Security rule, not tidiness. `integration_id` is writable on the
        # request serializer and `IntegrationHandler.get_integration` is a
        # global id lookup with no permission check, so a caller could point
        # this service at any integration in the instance. At dispatch,
        # `LocalBaserowServiceType.get_acting_user` prefers that integration's
        # `authorized_user` over the dispatch context's actor, which would make
        # every click run as the impersonated user. Database services are never
        # tied to an integration; the clicker is the acting user (ADR 006
        # section 5). Mirrors the hardcoded `None` in `deserialize_property`.
        service_values.pop("integration_id", None)
        prepared_service_values = service_type.prepare_values(
            service_values, user, service if instance else None
        )
        ServiceHandler().update_service(
            service_type, service, **prepared_service_values
        )

        values["service"] = service
        return super().prepare_values(values, user, instance)

    def import_serialized(
        self,
        parent,
        serialized_values,
        id_mapping,
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ):
        """
        Imports the action, and defers remapping the references inside the
        formulas its service stores, such as a field mapping value of
        `get('row.field_25')`.

        `deserialize_property` only reaches the FK-shaped references, so without
        this second step a duplicated table keeps a formula naming the original
        table's field and silently reads the wrong one (ADR 006 section 6).

        Deferred because a formula can name a field of an application that is
        not imported yet, so `id_mapping` does not know it.
        """

        created_instance = super().import_serialized(
            parent,
            serialized_values,
            id_mapping,
            files_zip,
            storage,
            cache,
            **kwargs,
        )

        def import_action_formulas():
            # `id_mapping` is the same dict throughout an import, so by now it
            # holds every application's ids.
            updated_models = self.import_formulas(
                created_instance, id_mapping, import_formula, **kwargs
            )
            for updated_model in updated_models:
                updated_model.save()

        register_deferred_callback(import_action_formulas)

        return created_instance

    def formula_generator(
        self, workflow_action: WorkflowAction
    ) -> Generator[str | Instance, str, None]:
        yield from super().formula_generator(workflow_action)

        service = workflow_action.service.specific
        yield from service.get_type().formula_generator(service)

    def enhance_queryset(self, queryset):
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
        self, workflow_action, dispatch_context: "DatabaseDispatchContext"
    ) -> DispatchResult:
        return ServiceHandler().dispatch_service(
            workflow_action.service.specific, dispatch_context
        )


class DatabaseWorkflowActionTypeRegistry(
    Registry, ModelRegistryMixin, CustomFieldsRegistryMixin
):
    """
    Contains all the registered workflow action types for the database module.
    """

    name = "database_workflow_action_type"


database_workflow_action_type_registry = DatabaseWorkflowActionTypeRegistry()
