from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import authenticate
from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError, connection, transaction

import pytest

from baserow.core.admin.dashboard.handler import AdminDashboardHandler
from baserow.core.admin.users.exceptions import UserDoesNotExistException
from baserow.core.admin.users.handler import UserAdminHandler
from baserow.core.agents.handler import AgentHandler
from baserow.core.handler import CoreHandler
from baserow.core.models import Agent, User
from baserow.core.operations import ReadWorkspaceOperationType
from baserow.core.registries import subject_type_registry
from baserow.core.trash.handler import TrashHandler
from baserow.core.user.exceptions import DeactivatedUserException, UserAlreadyExist
from baserow.core.user.handler import UserHandler


@pytest.mark.django_db
def test_agent_takes_its_users_id_and_cannot_sign_in(data_fixture):
    agent = data_fixture.create_agent(name="Ops")
    user = agent.user

    assert agent.id == user.id
    assert Agent.objects.get(user=user) == agent
    assert user.first_name == "Ops"
    assert user.email == user.username
    assert user.email.endswith("@agents.invalid")
    assert not user.is_active
    assert not user.has_usable_password()
    assert user.profile.timezone == "UTC"
    assert user.profile.email_notification_frequency == "never"
    assert not user.workspaceuser_set.exists()
    assert authenticate(username=user.username, password="password") is None
    assert not CoreHandler().check_permissions(
        user,
        ReadWorkspaceOperationType.type,
        workspace=agent.workspace,
        context=agent.workspace,
        raise_permission_exceptions=False,
    )


@pytest.mark.django_db
def test_agent_rejects_an_explicit_id_or_user_and_database_enforces_id(data_fixture):
    workspace = data_fixture.create_workspace()
    person = data_fixture.create_user()
    for kwargs in ({"id": person.id}, {"user": person}):
        with pytest.raises(ValueError):
            Agent.objects.create(workspace=workspace, name="Person", **kwargs)

    agent = data_fixture.create_agent(workspace=workspace)
    with pytest.raises(IntegrityError), transaction.atomic():
        Agent.objects.filter(id=agent.id).update(user=person)


@pytest.mark.django_db
def test_agent_rename_updates_its_user_and_trash_keeps_it(data_fixture):
    person = data_fixture.create_user()
    agent = data_fixture.create_agent(
        workspace=data_fixture.create_workspace(user=person)
    )
    AgentHandler().update_agent(agent, name="Support" * 22)
    agent.user.refresh_from_db()
    assert agent.user.first_name == agent.name[:150]

    AgentHandler().delete_agent(person, agent)
    assert User.objects_and_agents.filter(id=agent.user_id).exists()
    assert subject_type_registry.actor_for_user(agent.user) == agent
    agent_user_id = agent.user_id
    TrashHandler.permanently_delete(agent)
    assert not User.objects_and_agents.filter(id=agent_user_id).exists()


@pytest.mark.django_db
def test_workspace_deletion_deletes_its_agent_users(data_fixture):
    agent = data_fixture.create_agent()
    agent_user_id = agent.user_id
    agent.workspace.delete()
    assert not Agent.objects_and_trash.filter(id=agent.id).exists()
    assert not User.objects_and_agents.filter(id=agent_user_id).exists()


@pytest.mark.django_db
def test_actor_and_stored_user_conversions(data_fixture):
    person = data_fixture.create_user()
    inactive_person = data_fixture.create_user(is_active=False)
    agent = data_fixture.create_agent()
    token = data_fixture.create_token()

    assert subject_type_registry.user_for_actor(person) == person
    assert subject_type_registry.user_for_actor(agent) == agent.user
    assert subject_type_registry.user_for_actor(AnonymousUser()) is None
    assert subject_type_registry.user_for_actor(token) is None
    assert subject_type_registry.user_for_actor(None) is None
    assert subject_type_registry.actor_for_user(person) == person
    assert subject_type_registry.actor_for_user(inactive_person) == inactive_person
    assert subject_type_registry.actor_for_user(agent.user) == agent


@pytest.mark.django_db
def test_legacy_agent_does_not_capture_a_person_with_the_same_id(data_fixture):
    person = data_fixture.create_user(is_active=False)
    workspace = data_fixture.create_workspace()
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO core_agent (id, workspace_id, name, role_uid, trashed, "
            "created_on, updated_on) VALUES (%s, %s, 'Legacy', 'MEMBER', false, "
            "NOW(), NOW())",
            [person.id, workspace.id],
        )
    legacy = Agent.objects.get(id=person.id)
    assert subject_type_registry.user_for_actor(legacy) is None
    assert subject_type_registry.actor_for_user(person) == person
    with patch("baserow.core.models.create_agent_user", return_value=person):
        with pytest.raises(IntegrityError), transaction.atomic():
            Agent.objects.create(workspace=workspace, name="Cannot replace legacy")
    legacy.refresh_from_db()
    assert legacy.name == "Legacy"
    assert legacy.user_id is None
    AgentHandler().update_agent(legacy, name="Renamed legacy")
    assert list(User.objects.all()) == [person]
    legacy.delete()
    assert User.objects.filter(id=person.id).exists()


@pytest.mark.django_db
def test_people_only_queries_exclude_agent_users_including_trashed(data_fixture):
    person = data_fixture.create_user()
    agent = data_fixture.create_agent()
    agent.trashed = True
    agent.save(update_fields=["trashed"])

    assert list(User.objects.all()) == [person]
    historical_users = subject_type_registry.get(
        "auth.User"
    ).get_historical_options_queryset()
    assert [user["subject_id"] for user in historical_users] == [person.id]
    counts = AdminDashboardHandler().get_new_user_counts({"day": timedelta(days=1)})
    assert counts["day"] == 1
    daily_counts = AdminDashboardHandler().get_new_user_count_per_day(timedelta(days=1))
    assert sum(day["count"] for day in daily_counts) == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "method", ["update_user", "delete_user", "disable_user_two_factor_auth"]
)
def test_admin_cannot_change_agent_users(data_fixture, method):
    admin = data_fixture.create_user(is_staff=True)
    agent = data_fixture.create_agent()
    with pytest.raises(UserDoesNotExistException):
        getattr(UserAdminHandler(), method)(admin, agent.user_id)
    agent.user.refresh_from_db()
    assert not agent.user.is_active


@pytest.mark.django_db
@pytest.mark.parametrize(
    "operation", ["create", "confirm_email", "change_email", "admin"]
)
def test_people_cannot_take_an_agent_users_username(data_fixture, operation):
    password = "valid-password123"
    person = data_fixture.create_user(password=password)
    agent = data_fixture.create_agent()
    handler = UserHandler()

    if operation == "create":
        with pytest.raises(DeactivatedUserException):
            handler.force_create_user(
                email=agent.user.email, name="Person", password=password
            )
    elif operation == "confirm_email":
        data_fixture.create_password_provider()
        with pytest.raises(UserAlreadyExist):
            handler.send_change_email_confirmation(person, agent.user.email, password)
    elif operation == "change_email":
        token = handler.get_change_email_signer().dumps(
            {"user_id": person.id, "new_email": agent.user.email}
        )
        with pytest.raises(UserAlreadyExist):
            handler.change_email(token)
    else:
        admin = data_fixture.create_user(is_staff=True)
        with pytest.raises(UserAlreadyExist):
            UserAdminHandler().update_user(admin, person.id, username=agent.user.email)

    person.refresh_from_db()
    agent.user.refresh_from_db()
    assert person.email != agent.user.email
