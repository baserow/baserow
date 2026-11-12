from django.db import DEFAULT_DB_ALIAS

from baserow.config.celery import app
from baserow.config.db_routers import set_db_alias
from baserow.contrib.agent.models import AgentApplication
from baserow.contrib.agent.operations import ReadAgentConfigurationOperationType
from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace
from baserow.core.subjects import UserSubjectType
from baserow.core.types import PermissionCheck
from baserow.ws.tasks import broadcast_to_users_individual_payloads


@app.task
def broadcast_run_as_updates(workspace_id: int, identity_id: int) -> None:
    """Send one permission-filtered invalidation per user for an identity change.

    :param workspace_id: The workspace whose identity choices changed.
    :param identity_id: The changed identity, including a permanently deleted one.
    """

    # This task runs after commit; permission and selection reads must not lag it.
    set_db_alias(DEFAULT_DB_ALIAS)
    workspace = Workspace.objects.filter(id=workspace_id).first()
    if workspace is None:
        return

    applications = list(
        AgentApplication.objects.filter(workspace=workspace)
        .select_related("workspace")
        .order_by("id")
    )
    if not applications:
        return

    users = [
        membership.user
        for membership in workspace.workspaceuser_set.select_related("user")
    ]
    # Batch both actors and contexts so role assignments and scopes are loaded
    # once, rather than once per application in separate worker tasks.
    permissions = CoreHandler().check_multiple_permissions(
        [
            PermissionCheck(user, ReadAgentConfigurationOperationType.type, agent)
            for user in users
            for agent in applications
        ],
        workspace=workspace,
    )
    payload_map = {}
    for check, allowed in permissions.items():
        if not allowed:
            continue
        user, _, agent = check
        payload = payload_map.setdefault(
            str(user.id),
            {
                "type": "agent_run_as_updated",
                "agent_ids": [],
                "selected_agent_ids": [],
            },
        )
        payload["agent_ids"].append(agent.id)
        if (
            agent.run_as_subject_type == UserSubjectType.type
            and agent.run_as_subject_id == identity_id
        ):
            payload["selected_agent_ids"].append(agent.id)

    if payload_map:
        broadcast_to_users_individual_payloads(payload_map)
