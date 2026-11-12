from django.db import transaction

import pytest

from baserow.contrib.agent.models import AgentTrigger
from baserow.contrib.agent.triggers.exceptions import AgentTriggerDoesNotExist
from baserow.contrib.agent.triggers.service import AgentTriggerService
from baserow.contrib.agent.triggers.trash_types import AgentTriggerTrashableItemType
from baserow.core.exceptions import PermissionException
from baserow.core.trash.handler import TrashHandler
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role

CALLS = ["list", "get", "get_missing", "create", "update", "delete", "restore"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role_uid,allowed",
    [
        (None, False),
        ("NO_ACCESS", False),
        ("VIEWER", False),
        ("EDITOR", False),
        ("BUILDER", True),
        ("ADMIN", True),
    ],
    ids=["non-member", "no-access", "viewer", "editor", "builder", "admin"],
)
def test_only_builders_read_and_change_triggers(
    enterprise_data_fixture, enable_enterprise, synced_roles, role_uid, allowed
):
    admin = enterprise_data_fixture.create_user()
    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(
        user=admin, members=[user] if role_uid else []
    )
    if role_uid:
        RoleAssignmentHandler().assign_role(
            user, workspace, Role.objects.get(uid=role_uid)
        )
    agent = enterprise_data_fixture.create_agent_application(workspace=workspace)
    trigger = enterprise_data_fixture.create_agent_trigger(agent=agent)
    trashed = enterprise_data_fixture.create_agent_trigger(agent=agent)
    AgentTriggerService().delete_trigger(admin, agent.id, trashed.id)
    service = AgentTriggerService()
    attempts = {
        "list": lambda: service.list_triggers(user, agent.id),
        "get": lambda: service.get_trigger(user, agent.id, trigger.id),
        "get_missing": lambda: service.get_trigger(user, agent.id, trigger.id + 99),
        "create": lambda: service.create_trigger(user, agent.id, "periodic"),
        "update": lambda: service.update_trigger(
            user, agent.id, trigger.id, enabled=False
        ),
        "delete": lambda: service.delete_trigger(user, agent.id, trigger.id),
        "restore": lambda: TrashHandler.restore_item(
            user, AgentTriggerTrashableItemType.type, trashed.id
        ),
    }

    outcomes = {}
    for name in CALLS:
        try:
            with transaction.atomic():
                attempts[name]()
            outcomes[name] = "allowed"
        except PermissionException:
            outcomes[name] = "refused"
        except AgentTriggerDoesNotExist:
            outcomes[name] = "not found"

    expected = (
        {name: "allowed" for name in CALLS} | {"get_missing": "not found"}
        if allowed
        else {name: "refused" for name in CALLS}
    )
    assert outcomes == expected
    trigger.refresh_from_db()
    trashed.refresh_from_db()
    assert (
        AgentTrigger.objects_and_trash.count(),
        trigger.trashed,
        trashed.trashed,
    ) == ((3, True, False) if allowed else (2, False, True))
