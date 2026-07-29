from baserow.core.registries import OperationType


class DispatchDatabaseWorkflowActionOperationType(OperationType):
    """
    Clicking a button, as distinct from configuring it.

    Configuration follows field update permissions, so the builder role and
    above. Clicking is a lower bar: editor and above (ADR 006 section 7). A
    future per-field "who can click" permission attaches here.
    """

    type = "database.table.field.workflow_action.dispatch"
    context_scope_name = "database_workflow_action"
