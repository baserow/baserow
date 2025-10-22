from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.core.services.registries import service_type_registry


class AutomationWorkflowFixtures:
    def create_automation_workflow(self, user=None, **kwargs):
        # Do we want to create the trigger? We will by default.
        create_trigger = kwargs.pop("create_trigger", True)

        # Do we want to use a specific trigger type? The default is just
        # the first registered trigger type.
        first_trigger_type = [
            t for t in automation_node_type_registry.get_all() if t.is_workflow_trigger
        ][0]
        trigger_type = kwargs.pop("trigger_type", first_trigger_type)

        if isinstance(trigger_type, str):
            trigger_type = automation_node_type_registry.get(trigger_type)

        # Pluck out any values we need later for the trigger's service.
        trigger_service_kwargs = kwargs.pop("trigger_service_kwargs", {})

        if not kwargs.get("automation", None):
            if user is None:
                user = self.create_user()

            kwargs["automation"] = self.create_automation_application(user=user)

        if "name" not in kwargs:
            kwargs["name"] = self.fake.name()

        if "order" not in kwargs:
            kwargs["order"] = AutomationWorkflow.get_last_order(kwargs["automation"])

        workflow = AutomationWorkflow.objects.create(**kwargs)

        if create_trigger:
            # We must set the `application` so that the service's integration is
            # created in our automation application, otherwise a builder application
            # is created.
            trigger_service_kwargs["integration_args"] = {
                "application": kwargs["automation"]
            }
            service_type = service_type_registry.get(trigger_type.service_type)
            service = self.create_service(
                service_type.model_class, **trigger_service_kwargs
            )
            self.create_automation_node(
                workflow=workflow,
                type=trigger_type.type,
                service=service,
                reference_node_id=None,
                position="south",
                output="",
            )

        return workflow
