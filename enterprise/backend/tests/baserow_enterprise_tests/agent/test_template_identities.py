import json
from unittest.mock import patch

from django.db import transaction
from django.urls import reverse

import pytest
from rest_framework.status import HTTP_202_ACCEPTED

from baserow.contrib.agent.actions import UpdateAgentConfigurationActionType
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import AgentApplication
from baserow.contrib.database.models import Database
from baserow.core.action.registries import action_type_registry
from baserow.core.actions import InstallTemplateActionType
from baserow.core.exceptions import PermissionDenied
from baserow.core.handler import CoreHandler
from baserow.core.identities.handler import IdentityHandler
from baserow.core.identities.service import IdentityService
from baserow.core.job_types import InstallTemplateJobType
from baserow.core.jobs.constants import JOB_FINISHED
from baserow.core.jobs.handler import JobHandler
from baserow.core.models import Template, User
from baserow.core.registries import ImportExportConfig
from baserow.core.subjects import UserSubjectType
from baserow.core.user_templates.handler import UserTemplateHandler
from baserow_enterprise.audit_log.models import AuditLogEntry
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role, RoleAssignment

WRITE_TOOLS = (["create_rows", "list_tables"], ["create_rows"])
READ_TOOLS = (["list_tables", "list_table_rows"], [])


def export_for_template(applications) -> list[dict]:
    config = ImportExportConfig(include_permission_data=False)
    return json.loads(
        json.dumps(
            [
                application.get_type().export_serialized(application, config)
                for application in applications
            ]
        )
    )


def make_agent(fixture, workspace, name, tools):
    agent = fixture.create_agent_application(
        workspace=workspace,
        name=name,
        instructions="Help.",
        provider_type="openai",
        model_identifier="test-model",
    )
    identity = fixture.create_identity(workspace=workspace, name="Author")
    agent.run_as_subject_type, agent.run_as_subject_id = "auth.User", identity.id
    agent.save()
    allowed, ask_first = tools
    AgentHandler().set_allowed_tools(agent, allowed, ask_first_names=ask_first)
    return agent


def sync_template(
    fixture, settings, tmp_path, agents_tools, slug="agent-kit", with_database=True
):
    """An official template with a database and an Agent for each tool choice."""

    source = fixture.create_workspace()
    databases = (
        [fixture.create_database_application(workspace=source, name="CRM")]
        if with_database
        else []
    )
    agents = [
        make_agent(fixture, source, f"Agent {index}", tools)
        for index, tools in enumerate(agents_tools)
    ]
    (tmp_path / f"{slug}.json").write_text(
        json.dumps(
            {
                "baserow_template_version": 1,
                "name": "Agent kit",
                "icon": "iconoir-shop",
                "keywords": [],
                "categories": ["Agents"],
                "export": export_for_template([*databases, *agents]),
            }
        )
    )
    settings.APPLICATION_TEMPLATES_DIR = str(tmp_path)
    CoreHandler().sync_templates(pattern=slug)
    return Template.objects.get(slug=slug)


def install(user, workspace, template, **kwargs):
    job = JobHandler().create_and_start_job(
        user,
        InstallTemplateJobType.type,
        sync=True,
        workspace_id=workspace.id,
        template_id=template.id,
        **kwargs,
    )
    job.refresh_from_db()
    return job


def roles_of(identity):
    return set(
        RoleAssignment.objects.filter(subject_id=identity.id).values_list(
            "scope_id", "role__uid"
        )
    )


def run_identity(agent):
    agent.refresh_from_db()
    assert agent.run_as_subject_type == UserSubjectType.type
    return User.objects_and_identities.get(id=agent.run_as_subject_id)


@pytest.fixture
def admin(enterprise_data_fixture, enable_enterprise, synced_roles):
    return enterprise_data_fixture.create_user()


@pytest.mark.django_db(transaction=True)
def test_install_scopes_a_new_identity_to_the_template_databases(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(enterprise_data_fixture, settings, tmp_path, [WRITE_TOOLS])
    workspace = enterprise_data_fixture.create_workspace(user=admin)
    other_database = enterprise_data_fixture.create_database_application(
        workspace=workspace
    )

    job = install(admin, workspace, template, create_identities=True)

    assert job.state == JOB_FINISHED, job.human_readable_error
    agent = AgentApplication.objects.get(workspace=workspace)
    database = Database.objects.get(workspace=workspace, name="CRM")
    identity = run_identity(agent)
    assert identity.first_name == agent.name
    assert IdentityHandler.get_role_uid(identity) == "NO_ACCESS"
    assert roles_of(identity) == {(database.id, "EDITOR")}
    assert other_database.id not in {scope for scope, _ in roles_of(identity)}
    assert AgentHandler().get_tool_configuration(agent) == {
        "allowed_tools": ["list_tables", "create_rows"],
        "ask_first_tools": ["create_rows"],
    }
    assert agent.pending_tool_choices is None
    # Binding gives the identity's access to the Agent, so it's audited.
    assert AuditLogEntry.objects.filter(
        action_type=UpdateAgentConfigurationActionType.type,
        workspace_id=workspace.id,
    ).exists()


@pytest.mark.django_db(transaction=True)
def test_an_agent_that_only_reads_gets_a_viewer_identity(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(
        enterprise_data_fixture, settings, tmp_path, [READ_TOOLS, WRITE_TOOLS]
    )
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    install(admin, workspace, template, create_identities=True)

    database = Database.objects.get(workspace=workspace)
    reader, writer = AgentApplication.objects.filter(workspace=workspace).order_by(
        "name"
    )
    reader_identity, writer_identity = run_identity(reader), run_identity(writer)
    assert reader_identity.id != writer_identity.id
    assert roles_of(reader_identity) == {(database.id, "VIEWER")}
    assert roles_of(writer_identity) == {(database.id, "EDITOR")}


@pytest.mark.django_db(transaction=True)
def test_an_agent_only_template_creates_no_identity(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(
        enterprise_data_fixture,
        settings,
        tmp_path,
        [WRITE_TOOLS],
        with_database=False,
    )
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    job = install(admin, workspace, template, create_identities=True)

    assert job.state == JOB_FINISHED
    agent = AgentApplication.objects.get(workspace=workspace)
    assert agent.run_as_subject_id is None
    assert agent.pending_tool_choices is not None
    assert not IdentityHandler().get_queryset(workspace).exists()


@pytest.mark.django_db(transaction=True)
def test_without_the_option_the_agent_waits_for_an_identity(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(enterprise_data_fixture, settings, tmp_path, [WRITE_TOOLS])
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    job = install(admin, workspace, template)

    assert job.state == JOB_FINISHED
    agent = AgentApplication.objects.get(workspace=workspace)
    assert agent.run_as_subject_id is None
    assert agent.pending_tool_choices is not None
    assert not IdentityHandler().get_queryset(workspace).exists()


@pytest.mark.django_db(transaction=True)
def test_a_builder_cant_ask_for_identities(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(enterprise_data_fixture, settings, tmp_path, [WRITE_TOOLS])
    builder = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(
        users=[admin], custom_permissions=[(builder, "BUILDER")]
    )
    assert not IdentityService().can_create_scoped_identity(builder, workspace)

    with pytest.raises(PermissionDenied):
        install(builder, workspace, template, create_identities=True)

    assert not AgentApplication.objects.filter(workspace=workspace).exists()
    assert not IdentityHandler().get_queryset(workspace).exists()


@pytest.mark.django_db(transaction=True)
def test_without_rbac_identities_cant_be_scoped(
    enterprise_data_fixture, synced_roles, settings, tmp_path
):
    # No enterprise license, so an identity could only be a workspace member.
    template = sync_template(enterprise_data_fixture, settings, tmp_path, [WRITE_TOOLS])
    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    assert not IdentityService().can_create_scoped_identity(user, workspace)

    with pytest.raises(PermissionDenied):
        install(user, workspace, template, create_identities=True)

    assert not IdentityHandler().get_queryset(workspace).exists()


@pytest.mark.django_db(transaction=True)
def test_losing_rbac_before_the_job_runs_keeps_the_agent_pending(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(enterprise_data_fixture, settings, tmp_path, [WRITE_TOOLS])
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    with patch.object(
        IdentityService, "can_create_scoped_identity", side_effect=[True, False]
    ):
        job = install(admin, workspace, template, create_identities=True)

    assert job.state == JOB_FINISHED
    agent = AgentApplication.objects.get(workspace=workspace)
    assert agent.run_as_subject_id is None
    assert agent.pending_tool_choices is not None
    assert not IdentityHandler().get_queryset(workspace).exists()


@pytest.mark.django_db(transaction=True)
def test_a_failed_role_assignment_keeps_the_agent_pending_and_installs(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(enterprise_data_fixture, settings, tmp_path, [WRITE_TOOLS])
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    with patch.object(
        RoleAssignmentHandler,
        "assign_role_batch_for_user",
        side_effect=Role.DoesNotExist("boom"),
    ):
        job = install(admin, workspace, template, create_identities=True)

    assert job.state == JOB_FINISHED
    agent = AgentApplication.objects.get(workspace=workspace)
    assert Database.objects.filter(workspace=workspace).exists()
    assert agent.run_as_subject_id is None
    assert agent.pending_tool_choices == {
        "allowed_tools": ["list_tables", "create_rows"],
        "ask_first_tools": ["create_rows"],
    }
    # The identity of the failed Agent is rolled back with its roles.
    assert not IdentityHandler().get_queryset(workspace).exists()


@pytest.mark.django_db(transaction=True)
def test_the_install_endpoint_takes_the_option(
    enterprise_data_fixture, admin, settings, tmp_path, api_client
):
    template = sync_template(enterprise_data_fixture, settings, tmp_path, [WRITE_TOOLS])
    workspace = enterprise_data_fixture.create_workspace(user=admin)
    token = enterprise_data_fixture.generate_token(admin)
    url = reverse(
        "api:templates:install_async",
        kwargs={"workspace_id": workspace.id, "template_id": template.id},
    )

    response = api_client.post(
        f"{url}?create_identities=true", HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_202_ACCEPTED, response.json()
    agent = AgentApplication.objects.get(workspace=workspace)
    assert roles_of(run_identity(agent)) == {
        (Database.objects.get(workspace=workspace).id, "EDITOR")
    }


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_a_user_template_install_scopes_identities_too(enterprise_data_fixture, admin):
    source = enterprise_data_fixture.create_workspace(user=admin)
    database = enterprise_data_fixture.create_database_application(
        workspace=source, name="CRM"
    )
    agent = make_agent(enterprise_data_fixture, source, "Helper", READ_TOOLS)
    copy = UserTemplateHandler().copy_applications(
        admin, [database, agent], name="Copy"
    )
    revision = enterprise_data_fixture.create_user_template(user=admin, workspace=copy)
    content = UserTemplateHandler().serialize_template_content(revision)
    target = enterprise_data_fixture.create_workspace(user=admin)

    with transaction.atomic():
        action_type_registry.get_by_type(InstallTemplateActionType).do(
            admin, target, revision, content=content, create_identities=True
        )

    installed = AgentApplication.objects.get(workspace=target)
    assert roles_of(run_identity(installed)) == {
        (Database.objects.get(workspace=target).id, "VIEWER")
    }
    assert installed.pending_tool_choices is None
