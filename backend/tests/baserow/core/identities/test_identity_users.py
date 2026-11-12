from copy import deepcopy

from django.contrib.auth import get_user_model
from django.db import transaction

import pytest

from baserow.core.identities.handler import IdentityHandler
from baserow.core.models import UserProfile, Workspace, WorkspaceUser
from baserow.core.trash.handler import TrashHandler
from baserow.core.user.identity import is_human, is_identity

User = get_user_model()


@pytest.mark.django_db
def test_identity_is_a_single_user_with_an_owned_membership(data_fixture):
    workspace = data_fixture.create_workspace()
    identity = data_fixture.create_identity(workspace=workspace, name="Ops")
    assert identity.is_active
    assert is_identity(identity) and not is_human(identity)
    assert not identity.is_staff and not identity.is_superuser
    assert not identity.has_usable_password()
    assert identity.email == identity.username and identity.email.endswith(
        "@identities.invalid"
    )
    assert IdentityHandler.get_workspace(identity) == workspace
    assert IdentityHandler.get_role_uid(identity) == "MEMBER"
    membership = WorkspaceUser.objects_and_identities.get(user=identity)
    assert membership.workspace == workspace
    # Every other way to reach memberships hides the identity.
    assert not WorkspaceUser.objects.filter(user=identity).exists()
    assert not WorkspaceUser.objects_and_trash.filter(user=identity).exists()
    assert not workspace.workspaceuser_set.exists()
    assert not identity.workspaceuser_set.exists()


@pytest.mark.django_db
def test_people_manager_is_positive_lock_safe_and_base_manager_retains_identities(
    data_fixture,
):
    human = data_fixture.create_user(is_active=False)
    identity = data_fixture.create_identity(trashed=True)
    missing = User.objects_and_identities.create(username="missing-profile")
    assert list(deepcopy(User.objects.all())) == [human]
    with transaction.atomic():
        assert list(User.objects.select_for_update()) == [human]
    assert User._base_manager.get(id=identity.id) == identity
    assert User.objects_and_identities.get(id=missing.id) == missing
    assert not is_human(missing)
    human.profile.__dict__.pop("user_type")
    assert not is_human(human)


@pytest.mark.django_db
def test_trash_restore_keeps_identity_and_disabled_state(data_fixture):
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    identity = data_fixture.create_identity(workspace=workspace, is_active=False)
    IdentityHandler().delete_identity(admin, identity)
    assert WorkspaceUser.objects_and_identities.filter(user=identity).exists()
    assert not IdentityHandler().get_queryset(workspace).exists()
    restored = TrashHandler.restore_item(admin, "identity", identity.profile.id)
    assert restored.user_id == identity.id
    identity.refresh_from_db()
    assert not identity.is_active
    assert IdentityHandler().get_queryset(workspace).get() == identity


@pytest.mark.django_db
@pytest.mark.parametrize("delete", ["profile", "workspace", "workspace_queryset"])
def test_permanent_deletion_removes_owned_identity(data_fixture, delete):
    identity = data_fixture.create_identity(trashed=True)
    workspace = IdentityHandler.get_workspace(identity)
    identity_id = identity.id
    if delete == "profile":
        TrashHandler.permanently_delete(identity.profile)
    elif delete == "workspace":
        workspace.delete()
    else:
        Workspace.objects_and_trash.filter(id=workspace.id).delete()
    assert not User.objects_and_identities.filter(id=identity_id).exists()
    assert not UserProfile.objects_and_trash.filter(user_id=identity_id).exists()
    assert not WorkspaceUser.objects_and_identities.filter(user_id=identity_id).exists()


@pytest.mark.django_db
def test_generated_user_foreign_keys_keep_retained_identity_credits(data_fixture):
    table = data_fixture.create_database_table()
    field = data_fixture.create_created_by_field(table=table)
    identity = data_fixture.create_identity(
        workspace=table.database.workspace, trashed=True
    )
    model = table.get_model()
    row = model.objects.create(created_by_id=identity.id)
    row = model.objects.get(id=row.id)
    assert getattr(row, field.db_column) == identity
    row.refresh_from_db()
    assert row.created_by_id == identity.id


@pytest.mark.django_db
def test_standard_user_manager_creates_human_profiles():
    person = User.objects.create_user("person@example.com", password="password")
    admin = User.objects.create_superuser("admin@example.com", password="password")
    assert User.objects.get_by_natural_key(person.username) == person
    assert is_human(person) and is_human(admin)
    assert admin.is_staff and admin.is_superuser
