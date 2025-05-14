from functools import reduce

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.nodes.models import AutomationTriggerNode
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.core.services.registries import service_type_registry


def handle_local_baserow_row_trigger_signal(*args, **kwargs):
    """
    Responsible for handling Local Baserow trigger signals. This function is
    the same handler for all rows created, updated and deleted signals.
    """

    from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
    from baserow.contrib.automation.nodes.node_types import (
        signal_triggered_automation_triggers,
    )

    # Gather all trigger types that are triggered by Django
    # signals, then pluck out the service types from them.
    local_baserow_trigger_type_service_types = [
        tt.service_type for tt in signal_triggered_automation_triggers()
    ]

    # From that set of service types, gather the model classes for each of them.
    local_baserow_trigger_type_service_model_classes = [
        service_type_registry.get(st).model_class
        for st in local_baserow_trigger_type_service_types
    ]

    # For each model class, create a queryset that filters by the table that
    # was passed in the kwargs. Then, combine all of those querysets into one
    # using a union. This will give us a queryset of all the trigger services
    # that are associated with the table.
    trigger_services_qs = [
        model.objects.filter(table=kwargs["table"]).values_list("service_ptr")
        for model in local_baserow_trigger_type_service_model_classes
    ]
    trigger_services_qs = reduce(lambda x, y: x.union(y), trigger_services_qs)

    # Now that we have a queryset of all the trigger services, we can filter
    # the AutomationTriggerNode queryset by that queryset. This will give us
    # all the trigger nodes that are associated with the table.
    triggers = AutomationNodeHandler().get_nodes(
        base_queryset=AutomationTriggerNode.objects.filter(
            service__in=trigger_services_qs
        )
    )
    for trigger in triggers:
        AutomationWorkflowHandler().run_workflow(
            trigger.workflow,
            AutomationDispatchContext(
                trigger_input_data=kwargs, workflow=trigger.workflow
            ),
        )
