from unittest.mock import patch

from django.shortcuts import reverse

import pytest
from rest_framework.status import HTTP_202_ACCEPTED, HTTP_401_UNAUTHORIZED

from baserow.core.cache import local_cache
from baserow.core.job_types import InstallTemplateJobType
from baserow.core.jobs.constants import JOB_FAILED
from baserow.core.jobs.handler import JobHandler
from baserow.core.jobs.tasks import run_async_job
from baserow.core.models import (
    Application,
    InstallTemplateJob,
    Template,
    TemplateCategory,
)
from baserow.core.user_templates.job_types import CreateUserTemplateJobType
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import RoleAssignment


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_create_user_template_doesnt_copy_role_assignments(
    enterprise_data_fixture, enable_enterprise, synced_roles, use_tmp_media_root
):
    user = enterprise_data_fixture.create_user()
    member = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[member])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    admin = RoleAssignmentHandler().get_role_by_uid("ADMIN")
    viewer = RoleAssignmentHandler().get_role_by_uid("VIEWER")
    RoleAssignmentHandler().assign_role(user, workspace, role=admin, scope=workspace)
    RoleAssignmentHandler().assign_role(member, workspace, role=admin, scope=database)
    RoleAssignmentHandler().assign_role(member, workspace, role=viewer, scope=table)
    assignment_count = RoleAssignment.objects.count()

    JobHandler().create_and_start_job(
        user,
        CreateUserTemplateJobType.type,
        sync=True,
        workspace_id=workspace.id,
        application_ids=[database.id],
        name="My template",
        icon="iconoir-view-grid",
        category_ids=[TemplateCategory.objects.create(name="Cat").id],
    )

    # The members of the source workspace aren't members of the template.
    template_workspace = Template.objects.get().workspace
    assert not RoleAssignment.objects.filter(workspace=template_workspace).exists()
    assert RoleAssignment.objects.count() == assignment_count


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role_uid,expected_status",
    [
        ("ADMIN", HTTP_202_ACCEPTED),
        ("BUILDER", HTTP_202_ACCEPTED),
        ("EDITOR", HTTP_401_UNAUTHORIZED),
        ("COMMENTER", HTTP_401_UNAUTHORIZED),
        ("VIEWER", HTTP_401_UNAUTHORIZED),
        ("NO_ACCESS", HTTP_401_UNAUTHORIZED),
    ],
)
def test_install_user_template_target_roles(
    api_client,
    enterprise_data_fixture,
    enable_enterprise,
    synced_roles,
    role_uid,
    expected_status,
):
    user, token = enterprise_data_fixture.create_user_and_token()
    # Another admin, so that the role of the user can be lowered.
    admin = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=admin, members=[user])
    RoleAssignmentHandler().assign_role(
        user,
        workspace,
        role=RoleAssignmentHandler().get_role_by_uid(role_uid),
        scope=workspace,
    )
    user_template = enterprise_data_fixture.create_user_template(user=user)
    enterprise_data_fixture.create_database_application(
        workspace=user_template.workspace
    )

    response = api_client.post(
        reverse(
            "api:templates:install_async",
            kwargs={"workspace_id": workspace.id, "template_id": user_template.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == expected_status, response.json()
    jobs = InstallTemplateJob.objects.filter(workspace=workspace)
    if expected_status == HTTP_202_ACCEPTED:
        assert jobs.get().template_id == user_template.id
    else:
        assert response.json()["error"] == "PERMISSION_DENIED"
        assert not jobs.exists()


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_install_user_template_refused_when_the_role_is_lowered_before_it_runs(
    enterprise_data_fixture, enable_enterprise, synced_roles, use_tmp_media_root
):
    user = enterprise_data_fixture.create_user()
    admin = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=admin, members=[user])
    role_handler = RoleAssignmentHandler()
    role_handler.assign_role(
        user,
        workspace,
        role=role_handler.get_role_by_uid("BUILDER"),
        scope=workspace,
    )
    user_template = enterprise_data_fixture.create_user_template(user=user)
    enterprise_data_fixture.create_database_application(
        workspace=user_template.workspace
    )
    with patch("baserow.core.jobs.handler.run_async_job"):
        job = JobHandler().create_and_start_job(
            user,
            InstallTemplateJobType.type,
            workspace_id=workspace.id,
            template_id=user_template.id,
        )

    role_handler.assign_role(
        user,
        workspace,
        role=role_handler.get_role_by_uid("VIEWER"),
        scope=workspace,
    )
    # A worker clears the local cache before each task.
    local_cache.clear()
    run_async_job(job.id)

    job = InstallTemplateJob.objects.get(id=job.id)
    assert job.state == JOB_FAILED
    assert job.error_code == "PermissionException"
    assert not Application.objects_and_trash.filter(workspace=workspace).exists()
    assert Template.objects.get(id=user_template.id).install_count == 0
