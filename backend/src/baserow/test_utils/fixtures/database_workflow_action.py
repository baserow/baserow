from baserow.contrib.database.workflow_actions.models import (
    DatabaseWorkflowAction,
    DatabaseWorkflowServiceAction,
)


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
                service = self.create_local_baserow_upsert_row_service(integration=None)
            kwargs["service"] = service

        return action_type.objects.create(field=field, **kwargs)
