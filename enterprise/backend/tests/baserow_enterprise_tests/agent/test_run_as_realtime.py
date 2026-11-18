from django.db import connection
from django.test.utils import CaptureQueriesContext, override_settings

import pytest

from baserow.config.celery import clear_local
from baserow.contrib.agent.ws.tasks import broadcast_run_as_updates
from baserow.core.identities.handler import IdentityHandler
from baserow.core.identities.service import IdentityService
from baserow.core.subjects import UserSubjectType
from baserow.ws.tasks import broadcast_to_permitted_users
from baserow_enterprise.role.constants import BUILDER_ROLE_UID, VIEWER_ROLE_UID
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.teams.handler import TeamHandler


@pytest.mark.django_db
def test_identity_invalidation_reaches_application_builders_without_workspace_listing(
    enterprise_data_fixture,
    enable_enterprise,
    synced_roles,
    mocker,
    django_capture_on_commit_callbacks,
):
    admin = enterprise_data_fixture.create_user()
    builder = enterprise_data_fixture.create_user()
    viewer = enterprise_data_fixture.create_user()
    external = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(
        user=admin, members=[builder, viewer]
    )
    application = enterprise_data_fixture.create_agent_application(workspace=workspace)
    other_application = enterprise_data_fixture.create_agent_application(
        workspace=workspace
    )
    enterprise_data_fixture.create_agent_application(workspace=workspace, trashed=True)
    enterprise_data_fixture.create_agent_application(
        workspace=enterprise_data_fixture.create_workspace(user=external)
    )
    identity = IdentityHandler().create_identity(
        workspace=workspace, name="PRIVATE IDENTITY"
    )
    application.run_as_subject_type = UserSubjectType.type
    application.run_as_subject_id = identity.id
    application.save()
    roles = RoleAssignmentHandler()
    for user in [builder, viewer]:
        roles.assign_role(user, workspace, roles.get_role_by_uid(VIEWER_ROLE_UID))
    roles.assign_role(
        builder,
        workspace,
        roles.get_role_by_uid(BUILDER_ROLE_UID),
        scope=application.application_ptr,
    )
    # Execute the real recipient permission check, stopping at the channel send.
    queued = mocker.patch(
        "baserow.contrib.agent.ws.signals.broadcast_run_as_updates.delay",
        side_effect=broadcast_run_as_updates,
    )
    refreshes = mocker.patch(
        "baserow.contrib.agent.ws.tasks.broadcast_to_users_individual_payloads"
    )
    mocker.patch(
        "baserow.ws.signals.broadcast_to_permitted_users.delay",
        side_effect=broadcast_to_permitted_users,
    )
    sent = mocker.patch("baserow.ws.tasks.broadcast_to_users")

    with django_capture_on_commit_callbacks(execute=True):
        IdentityService().update_identity(admin, identity, name="PRIVATE NEW NAME")

    queued.assert_called_once_with(workspace.id, identity.id)
    refreshes.assert_called_once()
    payloads = refreshes.call_args.args[0]
    assert set(payloads) == {str(admin.id), str(builder.id)}
    for user, expected_ids in [
        (admin, {application.id, other_application.id}),
        (builder, {application.id}),
    ]:
        payload = payloads[str(user.id)]
        assert payload == {
            "type": "agent_run_as_updated",
            "agent_ids": payload["agent_ids"],
            "selected_agent_ids": [application.id],
        }
        assert set(payload["agent_ids"]) == expected_ids
    sent.assert_called_once()
    assert set(sent.call_args.args[0]) == {admin.id}
    assert sent.call_args.args[1]["type"] == "identity_updated"

    # A deleted workspace must not produce a stale invalidation either.
    workspace.trashed = True
    workspace.save(update_fields=["trashed"])
    refreshes.reset_mock()
    broadcast_run_as_updates(workspace.id, identity.id)
    refreshes.assert_not_called()


@pytest.mark.django_db
@override_settings(CACHALOT_ENABLED=False)
def test_identity_invalidation_batches_queries_and_tasks_across_applications(
    enterprise_data_fixture,
    enable_enterprise,
    synced_roles,
    mocker,
    django_capture_on_commit_callbacks,
):
    admin, builder, viewer = [enterprise_data_fixture.create_user() for _ in range(3)]
    workspace = enterprise_data_fixture.create_workspace(
        user=admin, members=[builder, viewer]
    )
    identity = IdentityHandler().create_identity(workspace=workspace, name="Identity")
    application = enterprise_data_fixture.create_agent_application(
        workspace=workspace,
        run_as_subject_type=UserSubjectType.type,
        run_as_subject_id=identity.id,
    )
    roles = RoleAssignmentHandler()
    for user in [builder, viewer]:
        roles.assign_role(user, workspace, roles.get_role_by_uid(VIEWER_ROLE_UID))
    roles.assign_role(
        builder,
        workspace,
        roles.get_role_by_uid(BUILDER_ROLE_UID),
        scope=application.application_ptr,
    )
    queued = mocker.patch(
        "baserow.contrib.agent.ws.signals.broadcast_run_as_updates.delay"
    )
    sent = mocker.patch(
        "baserow.contrib.agent.ws.tasks.broadcast_to_users_individual_payloads"
    )
    # Warm process-level metadata; each measured worker has a fresh task-local cache.
    broadcast_run_as_updates(workspace.id, identity.id)
    measurements = []
    for application_count in [1, 50]:
        if application_count > 1:
            for _ in range(application_count - 1):
                enterprise_data_fixture.create_agent_application(workspace=workspace)
        queued.reset_mock()
        with django_capture_on_commit_callbacks(execute=True):
            IdentityService().update_identity(
                admin, identity, name=f"Renamed with {application_count} applications"
            )
        queued.assert_called_once_with(workspace.id, identity.id)

        clear_local()
        sent.reset_mock()
        with CaptureQueriesContext(connection) as captured:
            broadcast_run_as_updates(*queued.call_args.args)
        measurements.append(captured.captured_queries)
        clear_local()
        sent.assert_called_once()
        payloads = sent.call_args.args[0]
        assert set(payloads) == {str(admin.id), str(builder.id)}
        assert len(payloads[str(admin.id)]["agent_ids"]) == application_count
        assert payloads[str(builder.id)]["agent_ids"] == [application.id]
        for payload in payloads.values():
            assert payload["selected_agent_ids"] == [application.id]

    assert len(measurements[0]) == len(measurements[1]), measurements


@pytest.mark.django_db
def test_team_rename_does_not_invalidate_identity_choices_per_member(
    enterprise_data_fixture,
    enable_enterprise,
    synced_roles,
    mocker,
    django_capture_on_commit_callbacks,
):
    admin = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=admin)
    identities = [
        IdentityHandler().create_identity(workspace=workspace, name=f"Identity {index}")
        for index in range(5)
    ]
    team = enterprise_data_fixture.create_team(workspace=workspace, members=identities)
    for identity in identities:
        enterprise_data_fixture.create_agent_application(
            workspace=workspace,
            run_as_subject_type=UserSubjectType.type,
            run_as_subject_id=identity.id,
        )
    queued = mocker.patch(
        "baserow.contrib.agent.ws.signals.broadcast_run_as_updates.delay"
    )
    management = mocker.patch("baserow.ws.signals.broadcast_to_permitted_users.delay")
    with django_capture_on_commit_callbacks(execute=True):
        TeamHandler().update_team(
            admin,
            team,
            "Renamed team",
            subjects=[
                {"subject_id": identity.id, "subject_type": UserSubjectType.type}
                for identity in identities
            ],
        )
    queued.assert_not_called()
    assert management.call_count == len(identities)
    assert {call.args[4]["identity"]["id"] for call in management.call_args_list} == {
        identity.id for identity in identities
    }
