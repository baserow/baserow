from django.db import connection
from django.test.utils import CaptureQueriesContext

import pytest

from baserow.core.exceptions import LastAdminOfWorkspace, WorkspaceUserIsLastAdmin
from baserow.core.handler import CoreHandler
from baserow.core.identities.operations import ListIdentitiesWorkspaceOperationType
from baserow.core.models import User, WorkspaceUser
from baserow.core.operations import (
    ListWorkspacesOperationType,
    ReadWorkspaceOperationType,
)
from baserow.core.permission_manager import WorkspaceMemberOnlyPermissionManagerType
from baserow.core.registries import subject_type_registry
from baserow.core.subjects import (
    HumanSubjectType,
    IdentitySubjectType,
    UserSubjectType,
)
from baserow.core.types import PermissionCheck


@pytest.mark.django_db
def test_workspace_role_availability_only_queries_identity_roles(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    user = User.objects.select_related("profile").get(id=user.id)
    subject = UserSubjectType()

    with django_assert_num_queries(0):
        assert subject.are_workspace_roles_available([user], workspace) == [True]


@pytest.mark.django_db
def test_registry_gives_each_user_type_its_own_subject_type(data_fixture):
    workspace = data_fixture.create_workspace()
    human = data_fixture.create_user(workspace=workspace)
    identity = data_fixture.create_identity(workspace=workspace)
    unknown = data_fixture.create_user(workspace=workspace)
    unknown.profile.user_type = "unknown"

    human_type = subject_type_registry.get_specific_type(human)
    identity_type = subject_type_registry.get_specific_type(identity)

    assert type(human_type) is HumanSubjectType
    assert type(identity_type) is IdentitySubjectType
    assert type(subject_type_registry.get_specific_type(unknown)) is HumanSubjectType
    assert type(subject_type_registry.get_by_model(identity)) is UserSubjectType
    assert human_type.type == identity_type.type == UserSubjectType.type
    assert human_type.is_interactive_user
    assert not identity_type.is_interactive_user
    with pytest.raises(NotImplementedError):
        _ = subject_type_registry.get_by_model(human).is_interactive_user


@pytest.mark.django_db
def test_stored_user_subject_type_answers_for_humans_and_identities_together(
    data_fixture,
):
    workspace = data_fixture.create_workspace()
    human = data_fixture.create_user(workspace=workspace)
    identity = data_fixture.create_identity(workspace=workspace)
    outsider = data_fixture.create_identity()
    stored_type = subject_type_registry.get(UserSubjectType.type)

    assert stored_type.are_in_workspace([identity, human, outsider], workspace) == [
        True,
        True,
        False,
    ]
    assert stored_type.get_label(human) == human.email
    assert stored_type.get_label(identity) == identity.first_name
    assert stored_type.get_users_included_in_subject(human) == [human]
    assert stored_type.get_users_included_in_subject(identity) == []


@pytest.mark.django_db
def test_identity_uses_user_subject_and_workspace_membership(data_fixture):
    workspace = data_fixture.create_workspace()
    identity = data_fixture.create_identity(workspace=workspace)
    subject = subject_type_registry.get_by_model(identity)

    assert isinstance(subject, UserSubjectType)
    assert not subject_type_registry.get_specific_type(identity).is_interactive_user
    assert subject.get_users_included_in_subject(identity) == []
    assert subject.is_in_workspace(identity, workspace)
    assert not subject.is_in_workspace(identity, data_fixture.create_workspace())
    assert subject_type_registry.get_subject("auth.User", identity.id) == identity


@pytest.mark.django_db
@pytest.mark.parametrize(
    "state", ["inactive", "trashed", "deleting", "workspace_trash", "extra_membership"]
)
@pytest.mark.parametrize("include_trash", [False, True])
def test_identity_membership_never_authorizes_unavailable_identity(
    data_fixture, state, include_trash
):
    workspace = data_fixture.create_workspace()
    identity = data_fixture.create_identity(workspace=workspace)
    if state == "inactive":
        identity.is_active = False
        identity.save()
    elif state == "trashed":
        identity.profile.trashed = True
        identity.profile.save()
    elif state == "deleting":
        identity.profile.to_be_deleted = True
        identity.profile.save()
    elif state == "workspace_trash":
        workspace.trashed = True
        workspace.save()
    else:
        data_fixture.create_user_workspace(user=identity)

    assert not UserSubjectType().is_in_workspace(identity, workspace, include_trash)
    manager = WorkspaceMemberOnlyPermissionManagerType()
    check = PermissionCheck(
        identity, ListIdentitiesWorkspaceOperationType.type, workspace
    )
    assert (
        manager.check_multiple_permissions([check], workspace, include_trash)[check]
        is not True
    )
    assert not manager.filter_queryset(
        identity, check.operation_name, User.objects_and_identities.all(), workspace
    )[0].exists()


@pytest.mark.django_db
def test_identity_has_no_global_or_public_template_permission(data_fixture):
    workspace = data_fixture.create_workspace()
    identity = data_fixture.create_identity(workspace=workspace, role_uid="ADMIN")
    template = data_fixture.create_template()
    handler = CoreHandler()

    assert not handler.check_permissions(
        identity, ListWorkspacesOperationType.type, raise_permission_exceptions=False
    )
    assert not handler.filter_queryset(
        identity, ListWorkspacesOperationType.type, User.objects_and_identities.all()
    ).exists()
    assert not handler.check_permissions(
        identity,
        ReadWorkspaceOperationType.type,
        workspace=template.workspace,
        context=template.workspace,
        raise_permission_exceptions=False,
    )
    assert handler.check_permissions(
        identity,
        ReadWorkspaceOperationType.type,
        workspace=workspace,
        context=workspace,
    )


@pytest.mark.django_db
def test_identity_admin_does_not_replace_last_human_admin(data_fixture):
    human = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=human)
    identity = data_fixture.create_identity(workspace=workspace, role_uid="ADMIN")
    handler = CoreHandler()
    membership = workspace.get_workspace_user(human)

    with pytest.raises(WorkspaceUserIsLastAdmin):
        handler.leave_workspace(human, workspace)
    with pytest.raises(LastAdminOfWorkspace):
        handler.force_update_workspace_user(None, membership, permissions="MEMBER")
    identity_membership = workspace.get_workspace_user(identity)
    for target_workspace in (workspace, data_fixture.create_workspace()):
        with pytest.raises(ValueError):
            handler.add_user_to_workspace(target_workspace, identity)
    with pytest.raises(ValueError):
        handler.leave_workspace(identity, workspace)
    with pytest.raises(ValueError):
        handler.delete_workspace_user(human, identity_membership)
    with pytest.raises(ValueError):
        handler.force_update_workspace_user(
            human, identity_membership, permissions="MEMBER"
        )
    assert WorkspaceUser.objects_and_identities.filter(user=identity).count() == 1


@pytest.mark.django_db
def test_membership_writes_of_a_person_take_no_row_lock(data_fixture):
    """The API locks the membership first, so a lock taken after it can deadlock."""

    admin, member = data_fixture.create_user(), data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[member])
    handler = CoreHandler()

    with CaptureQueriesContext(connection) as queries:
        handler.force_update_workspace_user(
            admin, workspace.get_workspace_user(member), permissions="ADMIN"
        )
        handler.leave_workspace(member, workspace)
        handler.add_user_to_workspace(workspace, member)
        handler.delete_workspace_user(admin, workspace.get_workspace_user(member))

    assert not [query["sql"] for query in queries if "UPDATE OF" in query["sql"]]


@pytest.mark.django_db
def test_subject_options_find_an_identity_by_its_name_only(data_fixture):
    workspace = data_fixture.create_workspace()
    person = data_fixture.create_user(workspace=workspace, email="jane@example.com")
    identity = data_fixture.create_identity(workspace=workspace, name="Ops bot")

    def found(search: str) -> list[int]:
        options = UserSubjectType().get_options_queryset(
            workspace=workspace, search=search
        )
        return [option["subject_id"] for option in options]

    assert found("ops") == [identity.id]
    assert found("example.com") == [person.id]
    assert found("identities.invalid") == []
    assert found("identity-") == []
