from copy import deepcopy

from django.contrib.auth import get_user_model
from django.db import transaction

import pytest

from baserow.core.agents.handler import AgentHandler
from baserow.core.models import UserProfile, Workspace, WorkspaceUser
from baserow.core.trash.handler import TrashHandler
from baserow.core.user.identity import is_agent_user, is_human_user

User = get_user_model()


@pytest.mark.django_db
def test_agent_is_a_single_user_with_an_owned_membership(data_fixture):
    workspace = data_fixture.create_workspace()
    agent = data_fixture.create_agent(workspace=workspace, name="Ops")
    assert agent.is_active
    assert is_agent_user(agent) and not is_human_user(agent)
    assert not agent.is_staff and not agent.is_superuser
    assert not agent.has_usable_password()
    assert agent.email == agent.username and agent.email.endswith("@agents.invalid")
    assert AgentHandler.get_workspace(agent) == workspace
    assert AgentHandler.get_role_uid(agent) == "MEMBER"
    assert WorkspaceUser.objects.agents().get(user=agent).workspace == workspace
    assert not WorkspaceUser.objects.people().filter(user=agent).exists()


@pytest.mark.django_db
def test_people_manager_is_positive_lock_safe_and_base_manager_retains_agents(
    data_fixture,
):
    human = data_fixture.create_user(is_active=False)
    agent = data_fixture.create_agent(trashed=True)
    missing = User.identities_and_trash.create(username="missing-profile")
    assert list(deepcopy(User.objects.all())) == [human]
    with transaction.atomic():
        assert list(User.objects.select_for_update()) == [human]
    assert User._base_manager.get(id=agent.id) == agent
    assert User.identities_and_trash.get(id=missing.id) == missing
    assert not is_human_user(missing)
    human.profile.__dict__.pop("identity_type")
    assert not is_human_user(human)


@pytest.mark.django_db
def test_identity_managers_include_agents_and_hide_trashed_ones(data_fixture):
    human = data_fixture.create_user(is_active=False)
    agent = data_fixture.create_agent()
    trashed_agent = data_fixture.create_agent(trashed=True)
    missing = User.identities_and_trash.create(username="missing-profile")

    assert set(User.identities.all()) == {human, agent, missing}
    assert set(User.identities_and_trash.all()) == {
        human,
        agent,
        trashed_agent,
        missing,
    }
    assert list(User.identities.agents()) == [agent]
    assert set(User.identities_and_trash.agents()) == {agent, trashed_agent}
    with transaction.atomic():
        assert set(User.identities.select_for_update()) == {human, agent, missing}


@pytest.mark.django_db
def test_trash_restore_keeps_identity_and_disabled_state(data_fixture):
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    agent = data_fixture.create_agent(workspace=workspace, is_active=False)
    AgentHandler().delete_agent(admin, agent)
    assert WorkspaceUser.objects_and_trash.filter(user=agent).exists()
    assert not AgentHandler().get_queryset(workspace).exists()
    restored = TrashHandler.restore_item(admin, "agent", agent.profile.id)
    assert restored.user_id == agent.id
    agent.refresh_from_db()
    assert not agent.is_active
    assert AgentHandler().get_queryset(workspace).get() == agent


@pytest.mark.django_db
@pytest.mark.parametrize("delete", ["profile", "workspace", "workspace_queryset"])
def test_permanent_deletion_removes_owned_identity(data_fixture, delete):
    agent = data_fixture.create_agent(trashed=True)
    workspace = AgentHandler.get_workspace(agent)
    agent_id = agent.id
    if delete == "profile":
        TrashHandler.permanently_delete(agent.profile)
    elif delete == "workspace":
        workspace.delete()
    else:
        Workspace.objects_and_trash.filter(id=workspace.id).delete()
    assert not User.identities_and_trash.filter(id=agent_id).exists()
    assert not UserProfile.objects_and_trash.filter(user_id=agent_id).exists()
    assert not WorkspaceUser.objects_and_trash.filter(user_id=agent_id).exists()


@pytest.mark.django_db
def test_generated_user_foreign_keys_keep_retained_agent_credits(data_fixture):
    table = data_fixture.create_database_table()
    field = data_fixture.create_created_by_field(table=table)
    agent = data_fixture.create_agent(workspace=table.database.workspace, trashed=True)
    model = table.get_model()
    row = model.objects.create(created_by_id=agent.id)
    row = model.objects.get(id=row.id)
    assert getattr(row, field.db_column) == agent
    row.refresh_from_db()
    assert row.created_by_id == agent.id


@pytest.mark.django_db
def test_standard_user_manager_creates_human_profiles():
    person = User.objects.create_user("person@example.com", password="password")
    admin = User.objects.create_superuser("admin@example.com", password="password")
    assert User.objects.get_by_natural_key(person.username) == person
    assert is_human_user(person) and is_human_user(admin)
    assert admin.is_staff and admin.is_superuser
