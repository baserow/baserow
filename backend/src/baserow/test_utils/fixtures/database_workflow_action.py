from baserow.contrib.database.workflow_actions.models import (
    DatabaseWorkflowAction,
    DatabaseWorkflowServiceAction,
)
from baserow.contrib.database.workflow_actions.registries import (
    database_workflow_action_type_registry,
)
from baserow.core.services.registries import service_type_registry


class DatabaseWorkflowActionFixtures:
    def create_database_workflow_action(
        self, action_type, field=None, service=None, **kwargs
    ):
        """
        Creates a workflow action of the given model class. Creates a button
        field and, for service-backed types, a service, when not supplied.
        """

        if field is None:
            field = self.create_button_field()

        if "order" not in kwargs:
            kwargs["order"] = DatabaseWorkflowAction.get_last_order(field)

        if issubclass(action_type, DatabaseWorkflowServiceAction):
            if service is None:
                # The service must match the action type, as `prepare_values`
                # only ever creates the type's own `service_type`.
                registry = database_workflow_action_type_registry
                action_type_instance = registry.get_by_model(action_type)
                service_type = service_type_registry.get(
                    action_type_instance.service_type
                )
                service = self.create_service(
                    service_type.model_class, integration=None
                )
            kwargs["service"] = service

        return action_type.objects.create(field=field, **kwargs)
