from baserow.contrib.database.workflow_actions.operations import (
    DispatchDatabaseWorkflowActionOperationType,
)
from baserow.core.registries import operation_type_registry


def test_the_dispatch_operation_is_registered():
    operation = operation_type_registry.get(
        DispatchDatabaseWorkflowActionOperationType.type
    )

    # The field, since that is all a grid cell has to ask the question with.
    assert operation.context_scope_name == "database_field"


def test_editors_may_dispatch_but_commenters_may_not():
    from baserow_enterprise.role.constants import (
        BUILDER_ROLE_UID,
        COMMENTER_ROLE_UID,
        EDITOR_ROLE_UID,
    )
    from baserow_enterprise.role.default_roles import default_roles

    assert DispatchDatabaseWorkflowActionOperationType in default_roles[EDITOR_ROLE_UID]
    assert (
        DispatchDatabaseWorkflowActionOperationType
        not in default_roles[COMMENTER_ROLE_UID]
    )
    assert (
        DispatchDatabaseWorkflowActionOperationType in default_roles[BUILDER_ROLE_UID]
    )
