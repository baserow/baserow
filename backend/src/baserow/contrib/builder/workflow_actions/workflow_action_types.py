from typing import Any, Dict, Generator, Union

from django.contrib.auth.models import AbstractUser

from rest_framework import serializers

from baserow.contrib.builder.api.workflow_actions.serializers import (
    PolymorphicServiceRequestSerializer,
    PolymorphicServiceSerializer,
)
from baserow.contrib.builder.elements.element_types import NavigationElementManager
from baserow.contrib.builder.formula_importer import import_formula
from baserow.contrib.builder.workflow_actions.models import (
    LocalBaserowCreateRowWorkflowAction,
    LocalBaserowDeleteRowWorkflowAction,
    LocalBaserowUpdateRowWorkflowAction,
    LogoutWorkflowAction,
    NotificationWorkflowAction,
    OpenPageWorkflowAction,
    RefreshDataSourceWorkflowAction,
)
from baserow.contrib.builder.workflow_actions.registries import (
    BuilderWorkflowActionType,
    builder_workflow_action_type_registry,
)
from baserow.contrib.builder.workflow_actions.types import BuilderWorkflowActionDict
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowDeleteRowServiceType,
    LocalBaserowUpsertRowServiceType,
)
from baserow.core.formula.serializers import FormulaSerializerField
from baserow.core.formula.types import BaserowFormula
from baserow.core.integrations.models import Integration
from baserow.core.registry import Instance
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.registries import service_type_registry
from baserow.core.workflow_actions.models import WorkflowAction


def service_backed_workflow_actions():
    """
    Responsible for returning all workflow action types which are backed by a service.
    We do this by checking if the workflow action type is a subclass of the base
    `BuilderWorkflowServiceActionType` class.

    :return: A list of workflow action types backed by a service.
    """

    return [
        workflow_action_type
        for workflow_action_type in builder_workflow_action_type_registry.get_all()
        if issubclass(workflow_action_type.__class__, BuilderWorkflowServiceActionType)
    ]


class NotificationWorkflowActionType(BuilderWorkflowActionType):
    type = "notification"
    model_class = NotificationWorkflowAction
    simple_formula_fields = ["title", "description"]
    serializer_field_names = ["title", "description"]
    serializer_field_overrides = {
        "title": FormulaSerializerField(
            help_text="The title of the notification. Must be an formula.",
            required=False,
            allow_blank=True,
            default="",
        ),
        "description": FormulaSerializerField(
            help_text="The description of the notification. Must be an formula.",
            required=False,
            allow_blank=True,
            default="",
        ),
    }

    class SerializedDict(BuilderWorkflowActionDict):
        title: BaserowFormula
        description: BaserowFormula

    @property
    def allowed_fields(self):
        return super().allowed_fields + ["title", "description"]

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, Any]:
        return {"title": "'hello'", "description": "'there'"}


class OpenPageWorkflowActionType(BuilderWorkflowActionType):
    type = "open_page"
    model_class = OpenPageWorkflowAction
    simple_formula_fields = NavigationElementManager.simple_formula_fields

    @property
    def serializer_field_names(self):
        return (
            super().serializer_field_names
            + NavigationElementManager.serializer_field_names
        )

    @property
    def allowed_fields(self):
        return super().allowed_fields + NavigationElementManager.allowed_fields

    @property
    def serializer_field_overrides(self):
        return (
            super().serializer_field_overrides
            | NavigationElementManager().get_serializer_field_overrides()
        )

    class SerializedDict(
        BuilderWorkflowActionDict,
        NavigationElementManager.SerializedDict,
    ):
        ...

    def get_pytest_params(self, pytest_data_fixture):
        return NavigationElementManager().get_pytest_params(pytest_data_fixture)

    def formula_generator(
        self, workflow_action: WorkflowAction
    ) -> Generator[str | Instance, str, None]:
        """
        Generator that iterates over formulas for the OpenPageWorkflowActionType.

        In addition to formula fields, formulas can also be stored in the
        page_parameters JSON field.
        """

        yield from super().formula_generator(workflow_action)

        for index, page_parameter in enumerate(workflow_action.page_parameters):
            new_formula = yield page_parameter.get("value")
            if new_formula is not None:
                workflow_action.page_parameters[index]["value"] = new_formula
                yield workflow_action

    def deserialize_property(
        self,
        prop_name,
        value,
        id_mapping: Dict,
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ) -> Any:
        return super().deserialize_property(
            prop_name,
            NavigationElementManager().deserialize_property(
                prop_name, value, id_mapping, **kwargs
            ),
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )


class LogoutWorkflowActionType(BuilderWorkflowActionType):
    type = "logout"
    model_class = LogoutWorkflowAction

    class SerializedDict(BuilderWorkflowActionDict):
        ...

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, Any]:
        return {}


class RefreshDataSourceWorkflowAction(BuilderWorkflowActionType):
    type = "refresh_data_source"
    model_class = RefreshDataSourceWorkflowAction
    serializer_field_names = ["data_source_id"]
    serializer_field_overrides = {
        "data_source_id": serializers.IntegerField(
            allow_null=True,
            default=None,
            required=False,
            help_text="The ID of the Data Source to be refreshed.",
        ),
    }

    class SerializedDict(BuilderWorkflowActionDict):
        data_source_id: int

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, Any]:
        return {}

    @property
    def allowed_fields(self):
        return super().allowed_fields + ["data_source_id"]

    def deserialize_property(
        self,
        prop_name,
        value,
        id_mapping: Dict,
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ) -> Any:
        data_sources = id_mapping.get("builder_data_sources", {})
        if prop_name == "data_source_id" and value in data_sources:
            return data_sources[value]

        return super().deserialize_property(
            prop_name,
            value,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )


class BuilderWorkflowServiceActionType(BuilderWorkflowActionType):
    service_type = None  # Must be implemented by subclasses.
    serializer_field_names = ["service"]
    request_serializer_field_overrides = {
        "service": PolymorphicServiceRequestSerializer(
            default=None,
            required=False,
            help_text="The service which this workflow action is associated with.",
        )
    }
    serializer_field_overrides = {
        "service": PolymorphicServiceSerializer(
            help_text="The service which this workflow action is associated with."
        )
    }
    request_serializer_field_names = ["service"]

    class SerializedDict(BuilderWorkflowActionDict):
        service: Dict

    @property
    def allowed_fields(self):
        return super().allowed_fields + ["service"]

    def get_pytest_params_serialized(
        self, pytest_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        service_type = service_type_registry.get_by_model(pytest_params["service"])
        return {"service": service_type.export_serialized(pytest_params["service"])}

    def serialize_property(
        self,
        workflow_action: WorkflowAction,
        prop_name: str,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        """
        You can customize the behavior of the serialization of a property with this
        hook.
        """

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
        id_mapping: Dict[str, Any],
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ) -> Any:
        """
        If the workflow action has a relation to a service, this method will
        map the service's new `integration_id` and call `import_service` on
        the serialized service values.

        :param prop_name: the name of the property being transformed.
        :param value: the value of this property.
        :param id_mapping: the id mapping dict.
        :return: the deserialized version for this property.
        """

        if prop_name == "service" and value:
            integration = None
            serialized_service = value
            integration_id = serialized_service.get("integration_id", None)
            if integration_id:
                integration_id = id_mapping["integrations"].get(
                    integration_id, integration_id
                )
                integration = Integration.objects.get(id=integration_id)

            return ServiceHandler().import_service(
                integration,
                serialized_service,
                id_mapping,
                storage=storage,
                cache=cache,
                files_zip=files_zip,
                import_formula=import_formula,
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
        instance: Union[
            LocalBaserowCreateRowWorkflowAction, LocalBaserowUpdateRowWorkflowAction
        ] = None,
    ):
        """
        Responsible for preparing the service based workflow action. By default,
        the only step is to pass any `service` data into the service.

        :param values: The full workflow action values to prepare.
        :param user: The user on whose behalf the change is made.
        :param instance: A `BuilderWorkflowServiceAction` subclass instance.
        :return: The modified workflow action values, prepared.
        """

        service_type = service_type_registry.get(self.service_type)

        if not instance:
            # If we haven't received a workflow action instance, we're preparing
            # as part of creating a new action. If this happens, we need to create
            # a new upsert row service.
            service = ServiceHandler().create_service(service_type)
        else:
            service = instance.service.specific

        # If we received any service values, prepare them.
        service_values = values.pop("service", None) or {}
        prepared_service_values = service_type.prepare_values(
            service_values, user, service
        )

        # Update the service instance with any prepared service values.
        ServiceHandler().update_service(
            service_type, service, **prepared_service_values
        )

        values["service"] = service
        return super().prepare_values(values, user, instance)

    def formula_generator(
        self, workflow_action: WorkflowAction
    ) -> Generator[str | Instance, str, None]:
        """
        This formula generator includes the service formulas.
        """

        yield from super().formula_generator(workflow_action)

        # Now yield from the service
        service = workflow_action.service.specific
        yield from service.get_type().formula_generator(service)


class UpsertRowWorkflowActionType(BuilderWorkflowServiceActionType):
    type = "upsert_row"
    service_type = LocalBaserowUpsertRowServiceType.type

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, int]:
        service = pytest_data_fixture.create_local_baserow_upsert_row_service()
        return {"service": service}


class CreateRowWorkflowActionType(UpsertRowWorkflowActionType):
    type = "create_row"
    model_class = LocalBaserowCreateRowWorkflowAction


class UpdateRowWorkflowActionType(UpsertRowWorkflowActionType):
    type = "update_row"
    model_class = LocalBaserowUpdateRowWorkflowAction


class DeleteRowWorkflowActionType(BuilderWorkflowServiceActionType):
    type = "delete_row"
    model_class = LocalBaserowDeleteRowWorkflowAction
    service_type = LocalBaserowDeleteRowServiceType.type

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, int]:
        service = pytest_data_fixture.create_local_baserow_delete_row_service()
        return {"service": service}
