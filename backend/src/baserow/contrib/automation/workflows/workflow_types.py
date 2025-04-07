from baserow.contrib.automation.models import AutomationWorkflow
from baserow.contrib.automation.workflows.registries import WorkflowType


class AutomationWorkflowType(WorkflowType):
    type = "automation_workflow"
    model_class = AutomationWorkflow
    serializer_field_names = []
    request_serializer_field_names = []
    request_serializer_field_overrides = {}
