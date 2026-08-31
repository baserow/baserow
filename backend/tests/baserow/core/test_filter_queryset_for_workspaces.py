from django.db.models import Q
from django.test.utils import override_settings

import pytest

from baserow.core.handler import CoreHandler
from baserow.core.models import Application
from baserow.core.operations import ListApplicationsWorkspaceOperationType
from baserow.core.registries import (
    PermissionManagerType,
    WorkspaceFilterDecision,
    permission_manager_type_registry,
)
from baserow.core.service import CoreService
from baserow.core.subjects import UserSubjectType

CORE_PERMISSION_MANAGERS = [
    "core",
    "setting_operation",
    "staff",
    "allow_if_template",
    "member",
    "token",
    "basic",
]


def _base_queryset(workspaces):
    return Application.objects.filter(workspace__in=workspaces).order_by(
        "workspace_id", "order", "id"
    )


@pytest.mark.django_db
@override_settings(PERMISSION_MANAGERS=CORE_PERMISSION_MANAGERS)
def test_filter_queryset_for_workspaces_fast_path_returns_same_queryset(data_fixture):
    user = data_fixture.create_user()
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace(user=user)
    data_fixture.create_database_application(workspace=workspace_1)
    data_fixture.create_database_application(workspace=workspace_2)

    workspaces = list(CoreHandler().list_user_workspaces(user))
    queryset = _base_queryset(workspaces)

    filtered = CoreHandler().filter_queryset_for_workspaces(
        user,
        ListApplicationsWorkspaceOperationType.type,
        queryset,
        workspaces,
    )

    # No manager restricts a member, so the very same queryset must be returned
    # without any extra WHERE clause.
    assert filtered is queryset


@pytest.mark.django_db
@override_settings(PERMISSION_MANAGERS=CORE_PERMISSION_MANAGERS)
def test_filter_queryset_for_workspaces_excludes_non_member_workspaces(data_fixture):
    user = data_fixture.create_user()
    workspace_member = data_fixture.create_workspace(user=user)
    workspace_other = data_fixture.create_workspace()
    app_member = data_fixture.create_database_application(workspace=workspace_member)
    data_fixture.create_database_application(workspace=workspace_other)

    workspaces = list(CoreHandler().get_enhanced_workspace_queryset().order_by("id"))
    queryset = _base_queryset(workspaces)

    filtered = CoreHandler().filter_queryset_for_workspaces(
        user,
        ListApplicationsWorkspaceOperationType.type,
        queryset,
        workspaces,
    )

    assert [a.id for a in filtered] == [app_member.id]


@pytest.mark.django_db
@override_settings(PERMISSION_MANAGERS=CORE_PERMISSION_MANAGERS)
def test_filter_queryset_for_workspaces_allows_template_workspaces(data_fixture):
    user = data_fixture.create_user()
    workspace_member = data_fixture.create_workspace(user=user)
    workspace_template = data_fixture.create_workspace()
    data_fixture.create_template(workspace=workspace_template)
    app_member = data_fixture.create_database_application(workspace=workspace_member)
    app_template = data_fixture.create_database_application(
        workspace=workspace_template
    )

    workspaces = sorted(
        CoreHandler()
        .get_enhanced_workspace_queryset()
        .filter(id__in=[workspace_member.id, workspace_template.id]),
        key=lambda w: w.id,
    )
    queryset = _base_queryset(workspaces)

    filtered = CoreHandler().filter_queryset_for_workspaces(
        user,
        ListApplicationsWorkspaceOperationType.type,
        queryset,
        workspaces,
    )

    # The user isn't a member of the template workspace, but the template
    # manager short-circuits the chain for that workspace before the member
    # manager can deny it.
    assert sorted(a.id for a in filtered) == sorted([app_member.id, app_template.id])


@pytest.mark.django_db
@override_settings(
    PERMISSION_MANAGERS=[*CORE_PERMISSION_MANAGERS, "legacy_single_workspace_stub"]
)
def test_filter_queryset_for_workspaces_legacy_manager_fallback(data_fixture):
    """
    A permission manager that only implements the single workspace
    `filter_queryset` must keep working through the default per workspace
    fallback of `filter_queryset_for_workspaces`.
    """

    class LegacySingleWorkspaceStubPermissionManagerType(PermissionManagerType):
        type = "legacy_single_workspace_stub"
        supported_actor_types = [UserSubjectType.type]
        calls = []

        def check_multiple_permissions(self, checks, workspace=None, **kwargs):
            return {}

        def filter_queryset(self, actor, operation_name, queryset, workspace=None):
            self.calls.append(workspace.id)
            # Restrict to the first application of the workspace, like a
            # legacy manager restricting per workspace would.
            first_app = (
                Application.objects.filter(workspace=workspace)
                .order_by("order", "id")
                .first()
            )
            return queryset.filter(id=first_app.id)

    permission_manager_type_registry.register(
        LegacySingleWorkspaceStubPermissionManagerType()
    )
    try:
        user = data_fixture.create_user()
        workspace_1 = data_fixture.create_workspace(user=user)
        workspace_2 = data_fixture.create_workspace(user=user)
        app_1a = data_fixture.create_database_application(workspace=workspace_1)
        data_fixture.create_database_application(workspace=workspace_1)
        app_2a = data_fixture.create_database_application(workspace=workspace_2)
        data_fixture.create_database_application(workspace=workspace_2)

        workspaces = list(CoreHandler().list_user_workspaces(user).order_by("id"))
        queryset = _base_queryset(workspaces)

        filtered = CoreHandler().filter_queryset_for_workspaces(
            user,
            ListApplicationsWorkspaceOperationType.type,
            queryset,
            workspaces,
        )

        # The fallback must have called the legacy method once per workspace and
        # the combined result must equal the per workspace restrictions.
        assert sorted(LegacySingleWorkspaceStubPermissionManagerType.calls) == sorted(
            [workspace_1.id, workspace_2.id]
        )
        assert [a.id for a in filtered] == [app_1a.id, app_2a.id]
    finally:
        permission_manager_type_registry.unregister("legacy_single_workspace_stub")


@pytest.mark.django_db
@override_settings(PERMISSION_MANAGERS=CORE_PERMISSION_MANAGERS)
def test_filter_queryset_for_workspaces_decision_q_and_deny(data_fixture):
    """
    Q and deny decisions of a batch aware manager are combined per workspace.
    """

    class BatchStubPermissionManagerType(PermissionManagerType):
        type = "batch_stub"
        supported_actor_types = [UserSubjectType.type]
        decisions_to_return = {}

        def check_multiple_permissions(self, checks, workspace=None, **kwargs):
            return {}

        def filter_queryset_for_workspaces(
            self, actor, operation_name, queryset, workspaces
        ):
            return self.decisions_to_return

    permission_manager_type_registry.register(BatchStubPermissionManagerType())
    try:
        user = data_fixture.create_user()
        workspace_1 = data_fixture.create_workspace(user=user)
        workspace_2 = data_fixture.create_workspace(user=user)
        workspace_3 = data_fixture.create_workspace(user=user)
        app_1a = data_fixture.create_database_application(workspace=workspace_1)
        data_fixture.create_database_application(workspace=workspace_1)
        data_fixture.create_database_application(workspace=workspace_2)
        app_3a = data_fixture.create_database_application(workspace=workspace_3)

        BatchStubPermissionManagerType.decisions_to_return = {
            workspace_1.id: WorkspaceFilterDecision(q=Q(id=app_1a.id)),
            workspace_2.id: WorkspaceFilterDecision(deny=True),
            # workspace_3 is omitted: unrestricted.
        }

        with override_settings(
            PERMISSION_MANAGERS=[*CORE_PERMISSION_MANAGERS, "batch_stub"]
        ):
            workspaces = list(CoreHandler().list_user_workspaces(user).order_by("id"))
            queryset = _base_queryset(workspaces)

            filtered = CoreHandler().filter_queryset_for_workspaces(
                user,
                ListApplicationsWorkspaceOperationType.type,
                queryset,
                workspaces,
            )

        assert [a.id for a in filtered] == [app_1a.id, app_3a.id]
    finally:
        permission_manager_type_registry.unregister("batch_stub")


@pytest.mark.django_db
@override_settings(PERMISSION_MANAGERS=CORE_PERMISSION_MANAGERS)
def test_list_applications_in_workspaces_equals_per_workspace_listing(data_fixture):
    user = data_fixture.create_user()
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace(user=user)
    data_fixture.create_database_application(workspace=workspace_1, order=2)
    data_fixture.create_database_application(workspace=workspace_1, order=1)
    data_fixture.create_builder_application(workspace=workspace_2)
    data_fixture.create_dashboard_application(workspace=workspace_2)
    data_fixture.create_automation_application(workspace=workspace_2)

    workspaces = list(CoreHandler().list_user_workspaces(user).order_by("id"))

    batched = list(CoreService().list_applications_in_workspaces(user, workspaces))

    per_workspace = []
    for workspace in workspaces:
        per_workspace.extend(
            CoreService()
            .list_applications_in_workspace(user, workspace)
            .order_by("order", "id")
        )

    assert [(a.id, type(a)) for a in batched] == [
        (a.id, type(a)) for a in per_workspace
    ]


@pytest.mark.django_db
@override_settings(PERMISSION_MANAGERS=CORE_PERMISSION_MANAGERS)
def test_filter_queryset_for_workspaces_combines_decisions_of_multiple_managers(
    data_fixture,
):
    """
    Decisions of multiple managers for the same workspace must all apply, like
    the sequential `filter_queryset` chain would, including subquery shaped Qs.
    """

    class RestrictingStubPermissionManagerType(PermissionManagerType):
        supported_actor_types = [UserSubjectType.type]
        decisions_to_return = {}

        def check_multiple_permissions(self, checks, workspace=None, **kwargs):
            return {}

        def filter_queryset_for_workspaces(
            self, actor, operation_name, queryset, workspaces
        ):
            return self.decisions_to_return

    class StubAPermissionManagerType(RestrictingStubPermissionManagerType):
        type = "combine_stub_a"

    class StubBPermissionManagerType(RestrictingStubPermissionManagerType):
        type = "combine_stub_b"

    permission_manager_type_registry.register(StubAPermissionManagerType())
    permission_manager_type_registry.register(StubBPermissionManagerType())
    try:
        user = data_fixture.create_user()
        workspace_1 = data_fixture.create_workspace(user=user)
        workspace_2 = data_fixture.create_workspace(user=user)
        app_1a = data_fixture.create_database_application(workspace=workspace_1)
        app_1b = data_fixture.create_database_application(workspace=workspace_1)
        data_fixture.create_database_application(workspace=workspace_1)
        app_2a = data_fixture.create_database_application(workspace=workspace_2)
        data_fixture.create_database_application(workspace=workspace_2)

        # Manager A allows {app_1a, app_1b} via a subquery shaped Q, manager B
        # allows {app_1b} via an id list: only the intersection must survive.
        StubAPermissionManagerType.decisions_to_return = {
            workspace_1.id: WorkspaceFilterDecision(
                q=Q(
                    pk__in=Application.objects.filter(
                        id__in=[app_1a.id, app_1b.id]
                    ).values("pk")
                )
            ),
            workspace_2.id: WorkspaceFilterDecision(q=Q(id=app_2a.id)),
        }
        StubBPermissionManagerType.decisions_to_return = {
            workspace_1.id: WorkspaceFilterDecision(q=Q(id__in=[app_1b.id])),
        }

        with override_settings(
            PERMISSION_MANAGERS=[
                *CORE_PERMISSION_MANAGERS,
                "combine_stub_a",
                "combine_stub_b",
            ]
        ):
            workspaces = list(CoreHandler().list_user_workspaces(user).order_by("id"))
            queryset = _base_queryset(workspaces)

            filtered = CoreHandler().filter_queryset_for_workspaces(
                user,
                ListApplicationsWorkspaceOperationType.type,
                queryset,
                workspaces,
            )

        assert [a.id for a in filtered] == [app_1b.id, app_2a.id]
    finally:
        permission_manager_type_registry.unregister("combine_stub_a")
        permission_manager_type_registry.unregister("combine_stub_b")
