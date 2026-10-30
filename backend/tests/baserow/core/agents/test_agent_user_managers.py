from copy import deepcopy

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser, UserManager
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.state import ModelState

import pytest

from baserow.core.user.managers import (
    PeopleUserQuerySet,
    UsersAndAgentsManager,
    install_user_managers,
)

User = get_user_model()


@pytest.mark.django_db
@pytest.mark.parametrize("trashed", [False, True])
def test_default_user_manager_excludes_agents_including_trashed(data_fixture, trashed):
    person = data_fixture.create_user()
    inactive_person = data_fixture.create_user(is_active=False)
    agent = data_fixture.create_agent()
    if trashed:
        agent.trashed = True
        agent.save(update_fields=["trashed"])

    assert set(User.objects.all()) == {person, inactive_person}
    assert set(deepcopy(User.objects.all())) == {person, inactive_person}
    assert not User.objects.filter(id=agent.user_id).exists()
    assert set(User._default_manager.all()) == {person, inactive_person}
    assert set(User.objects_and_agents.all()) == {person, inactive_person, agent.user}
    assert User.objects_and_agents.get(id=agent.user_id) == agent.user
    assert User._base_manager.get(id=agent.user_id) == agent.user
    assert User.objects.select_for_update().get(id=person.id) == person

    agent_user = agent.user
    agent.refresh_from_db()
    assert agent.user == agent_user
    with pytest.raises(User.DoesNotExist):
        User.objects.get_by_natural_key(agent_user.username)


@pytest.mark.django_db
def test_user_manager_preserves_django_creation_and_natural_keys():
    person = User.objects.create_user(
        username="person@example.com", email="person@example.com", password="secret"
    )
    admin = User.objects.create_superuser(
        username="admin@example.com", email="admin@example.com", password="secret"
    )

    assert User.objects.get_by_natural_key(person.username) == person
    assert person.check_password("secret")
    assert admin.is_staff and admin.is_superuser
    assert type(User.objects) is UserManager
    assert isinstance(User.objects_and_agents, UsersAndAgentsManager)


def test_installing_user_managers_is_idempotent_and_concrete_user_only():
    original_default = User.objects
    original_inclusive = User.objects_and_agents
    local_manager_count = len(User._meta.local_managers)

    install_user_managers()
    install_user_managers()

    assert User.objects is original_default
    assert User.objects_and_agents is original_inclusive
    assert len(User._meta.local_managers) == local_manager_count
    assert User.objects._queryset_class is PeopleUserQuerySet
    assert User.objects.db_manager("default-copy").all().db == "default-copy"
    assert not hasattr(AbstractUser, "objects_and_agents")
    assert (
        AbstractUser._meta.managers_map["objects"]._queryset_class
        is not PeopleUserQuerySet
    )


def test_auth_migration_state_and_historical_managers_are_unchanged():
    loader = MigrationLoader(None)
    auth_leaves = [node for node in loader.graph.leaf_nodes() if node[0] == "auth"]
    historical_state = loader.project_state(auth_leaves)
    historical_model_state = historical_state.models[("auth", "user")]
    runtime_model_state = ModelState.from_model(User)

    assert runtime_model_state.managers == historical_model_state.managers
    assert [
        (name, manager.deconstruct()) for name, manager in runtime_model_state.managers
    ] == [
        (name, manager.deconstruct())
        for name, manager in historical_model_state.managers
    ]
    assert [name for name, _ in runtime_model_state.managers] == ["objects"]

    historical_user = historical_state.apps.get_model("auth", "User")
    assert type(historical_user.objects) is UserManager
    assert "core_agent" not in str(historical_user.objects.all().query)
    assert not hasattr(historical_user, "objects_and_agents")
