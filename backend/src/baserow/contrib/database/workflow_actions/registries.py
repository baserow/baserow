from typing import Any, Dict, Generator

from django.contrib.auth.models import AbstractUser
from django.db.models import Prefetch

from baserow.api.services.serializers import (
    PolymorphicServiceRequestSerializer,
    PolymorphicServiceSerializer,
)
from baserow.contrib.database.workflow_actions.types import DatabaseWorkflowActionDict
from baserow.core.db import specific_queryset
from baserow.core.registry import (
    CustomFieldsInstanceMixin,
    CustomFieldsRegistryMixin,
    Instance,
    ModelRegistryMixin,
    Registry,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.models import Service
from baserow.core.services.registries import service_type_registry
from baserow.core.workflow_actions.models import WorkflowAction
from baserow.core.workflow_actions.registries import WorkflowActionType


class DatabaseWorkflowActionType(WorkflowActionType, CustomFieldsInstanceMixin):
    allowed_fields = ["order", "field", "field_id"]
    parent_property_name = "field"
    id_mapping_name = "database_workflow_actions"

    class SerializedDict(DatabaseWorkflowActionDict):
        pass

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, Any]:
        return {}

    def dispatch(self, workflow_action, dispatch_context):
        # Dispatch arrives in phase 2c together with the endpoint that calls it.
        raise NotImplementedError()


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
        prepared_service_values = service_type.prepare_values(
            service_values, user, service if instance else None
        )
        ServiceHandler().update_service(
            service_type, service, **prepared_service_values
        )

        values["service"] = service
        return super().prepare_values(values, user, instance)

    # TODO: nothing consumes this generator yet, so service formulas are not
    # remapped on import. Wiring it needs an `import_serialized` override on
    # this class that calls `self.import_formulas(created_instance, id_mapping,
    # import_formula)` with a database-side `import_formula`, the way
    # `BuilderWorkflowActionType.import_serialized` does. That `import_formula`
    # does not exist yet: the database module registers no data providers, so a
    # stored formula cannot reference anything importable and there is nothing
    # to remap against. Wire both together when dispatch data providers land.
    # FK-shaped references are unaffected; `LocalBaserowUpsertRowServiceType`
    # already remaps `field_mappings[].field_id` in `deserialize_property`.
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


class DatabaseWorkflowActionTypeRegistry(
    Registry, ModelRegistryMixin, CustomFieldsRegistryMixin
):
    """
    Contains all the registered workflow action types for the database module.
    """

    name = "database_workflow_action_type"


database_workflow_action_type_registry = DatabaseWorkflowActionTypeRegistry()
