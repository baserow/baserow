import json
from unittest.mock import patch

from django.db import transaction
from django.urls import reverse

import pytest
from rest_framework.status import HTTP_202_ACCEPTED

from baserow.contrib.agent.actions import UpdateAgentConfigurationActionType
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import AgentApplication
from baserow.contrib.builder.models import Builder
from baserow.contrib.database.models import Database
from baserow.core.action.registries import action_type_registry
from baserow.core.actions import InstallTemplateActionType
from baserow.core.exceptions import PermissionDenied, PermissionException
from baserow.core.handler import CoreHandler
from baserow.core.identities.actions import CreateIdentityActionType
from baserow.core.identities.exceptions import IdentityCannotBeScoped
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
from baserow_enterprise.exceptions import ScopeNotExist
from baserow_enterprise.identities.identity_extension_types import (
    EnterpriseIdentityExtensionType,
)
from baserow_enterprise.role.actions import BatchAssignRoleActionType
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role, RoleAssignment
from baserow_enterprise.role.types import NewRoleAssignment

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


def make_agent(fixture, workspace, name, tools, identity=None):
    agent = fixture.create_agent_application(
        workspace=workspace,
        name=name,
        instructions="Help.",
        provider_type="openai",
        model_identifier="test-model",
    )
    # With workspace access, its roles aren't exported, so the tools pick them.
    identity = identity or fixture.create_identity(
        workspace=workspace, name="Author", role_uid="BUILDER"
    )
    agent.run_as_subject_type, agent.run_as_subject_id = "auth.User", identity.id
    agent.save()
    allowed, ask_first = tools
    AgentHandler().set_allowed_tools(agent, allowed, ask_first_names=ask_first)
    return agent


def sync_template(
    fixture,
    settings,
    tmp_path,
    agents_tools,
    slug="agent-kit",
    with_database=True,
    with_site=False,
    source_roles=None,
):
    """
    An official template with a database and an Agent for each tool choice. With
    `source_roles`, the Agents act as one identity without workspace access that has
    those roles, by application name, in the source workspace.
    """

    source = fixture.create_workspace()
    applications = []
    if with_database:
        applications.append(
            fixture.create_database_application(workspace=source, name="CRM")
        )
    if with_site:
        applications.append(
            fixture.create_builder_application(workspace=source, name="Site")
        )
    identity = None
    if source_roles is not None:
        identity = fixture.create_identity(
            workspace=source, name="Author", role_uid="NO_ACCESS"
        )
        by_name = {application.name: application for application in applications}
        RoleAssignmentHandler().assign_role_batch(
            source,
            [
                NewRoleAssignment(
                    identity,
                    Role.objects.get(uid=role_uid),
                    by_name[name].application_ptr,
                )
                for name, role_uid in source_roles.items()
            ],
        )
    agents = [
        make_agent(fixture, source, f"Agent {index}", tools, identity)
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
                "export": export_for_template([*applications, *agents]),
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
def test_install_scopes_a_new_identity_to_the_template_applications(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(
        enterprise_data_fixture, settings, tmp_path, [WRITE_TOOLS], with_site=True
    )
    workspace = enterprise_data_fixture.create_workspace(user=admin)
    other_database = enterprise_data_fixture.create_database_application(
        workspace=workspace
    )

    job = install(admin, workspace, template, create_identities=True)

    assert job.state == JOB_FINISHED, job.human_readable_error
    agent = AgentApplication.objects.get(workspace=workspace)
    database = Database.objects.get(workspace=workspace, name="CRM")
    site = Builder.objects.get(workspace=workspace, name="Site")
    identity = run_identity(agent)
    assert identity.first_name == agent.name
    assert IdentityHandler.get_role_uid(identity) == "NO_ACCESS"
    # Not on the Agent itself, so it can't change its own configuration.
    assert roles_of(identity) == {(database.id, "BUILDER"), (site.id, "BUILDER")}
    assert other_database.id not in {scope for scope, _ in roles_of(identity)}
    assert AgentHandler().get_tool_configuration(agent) == {
        "allowed_tools": ["list_tables", "create_rows"],
        "ask_first_tools": ["create_rows"],
    }
    assert agent.pending_tool_choices is None
    # Creating, scoping and binding the identity are all audited.
    assert set(
        AuditLogEntry.objects.filter(workspace_id=workspace.id).values_list(
            "action_type", flat=True
        )
    ) >= {
        CreateIdentityActionType.type,
        BatchAssignRoleActionType.type,
        UpdateAgentConfigurationActionType.type,
    }


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
    assert roles_of(writer_identity) == {(database.id, "BUILDER")}


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
def test_a_builder_can_ask_for_identities(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(enterprise_data_fixture, settings, tmp_path, [WRITE_TOOLS])
    builder = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(
        users=[admin], custom_permissions=[(builder, "BUILDER")]
    )
    # Builders can't create identities or assign roles themselves.
    assert not CoreHandler().check_permissions(
        builder,
        "identity.create",
        workspace=workspace,
        context=workspace,
        raise_permission_exceptions=False,
    )
    assert IdentityService().can_create_scoped_identity(builder, workspace)

    job = install(builder, workspace, template, create_identities=True)

    assert job.state == JOB_FINISHED, job.human_readable_error
    agent = AgentApplication.objects.get(workspace=workspace)
    identity = run_identity(agent)
    assert IdentityHandler.get_role_uid(identity) == "NO_ACCESS"
    assert roles_of(identity) == {
        (Database.objects.get(workspace=workspace).id, "BUILDER")
    }
    assert agent.pending_tool_choices is None


@pytest.mark.django_db(transaction=True)
def test_a_role_without_the_permission_cant_ask_for_identities(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(enterprise_data_fixture, settings, tmp_path, [WRITE_TOOLS])
    builder = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(
        users=[admin], custom_permissions=[(builder, "BUILDER")]
    )

    with (
        patch.object(IdentityService, "can_create_scoped_identity", return_value=False),
        pytest.raises(PermissionDenied),
    ):
        install(builder, workspace, template, create_identities=True)

    assert not AgentApplication.objects.filter(workspace=workspace).exists()
    assert not IdentityHandler().get_queryset(workspace).exists()


@pytest.mark.django_db(transaction=True)
def test_scoping_refuses_an_application_the_installer_cant_update(
    enterprise_data_fixture, admin
):
    builder = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(
        users=[admin], custom_permissions=[(builder, "BUILDER")]
    )
    hidden = enterprise_data_fixture.create_database_application(workspace=workspace)
    RoleAssignmentHandler().assign_role(
        builder, workspace, role=Role.objects.get(uid="NO_ACCESS"), scope=hidden
    )

    with pytest.raises(PermissionException):
        IdentityService().create_scoped_identity(
            builder,
            workspace,
            name="Helper",
            applications=[hidden],
            can_change_data=True,
        )

    assert not IdentityHandler().get_queryset(workspace).exists()


@pytest.mark.django_db(transaction=True)
def test_the_template_identity_roles_are_recreated(
    enterprise_data_fixture, admin, settings, tmp_path
):
    # Tools that change data, but the template's identity only views the database.
    template = sync_template(
        enterprise_data_fixture,
        settings,
        tmp_path,
        [WRITE_TOOLS],
        with_site=True,
        source_roles={"CRM": "VIEWER"},
    )
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    install(admin, workspace, template, create_identities=True)

    identity = run_identity(AgentApplication.objects.get(workspace=workspace))
    assert IdentityHandler.get_role_uid(identity) == "NO_ACCESS"
    assert roles_of(identity) == {
        (Database.objects.get(workspace=workspace).id, "VIEWER")
    }


@pytest.mark.django_db(transaction=True)
def test_an_admin_role_on_an_application_isnt_recreated(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(
        enterprise_data_fixture,
        settings,
        tmp_path,
        [WRITE_TOOLS],
        with_site=True,
        source_roles={"CRM": "ADMIN", "Site": "VIEWER"},
    )
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    install(admin, workspace, template, create_identities=True)

    identity = run_identity(AgentApplication.objects.get(workspace=workspace))
    assert roles_of(identity) == {
        (Builder.objects.get(workspace=workspace).id, "VIEWER")
    }


@pytest.mark.django_db(transaction=True)
def test_only_builder_and_viewer_roles_are_recreated(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(
        enterprise_data_fixture,
        settings,
        tmp_path,
        [WRITE_TOOLS],
        with_site=True,
        source_roles={"CRM": "EDITOR", "Site": "COMMENTER"},
    )
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    install(admin, workspace, template, create_identities=True)

    identity = run_identity(AgentApplication.objects.get(workspace=workspace))
    assert roles_of(identity) == {
        (Database.objects.get(workspace=workspace).id, "BUILDER"),
        (Builder.objects.get(workspace=workspace).id, "VIEWER"),
    }


@pytest.mark.django_db(transaction=True)
def test_an_identity_without_application_roles_isnt_recreated(
    enterprise_data_fixture, admin, settings, tmp_path
):
    # The template's identity could reach none of its applications.
    template = sync_template(
        enterprise_data_fixture,
        settings,
        tmp_path,
        [WRITE_TOOLS],
        source_roles={},
    )
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    job = install(admin, workspace, template, create_identities=True)

    assert job.state == JOB_FINISHED
    agent = AgentApplication.objects.get(workspace=workspace)
    assert agent.run_as_subject_id is None
    assert agent.pending_tool_choices is not None
    assert not IdentityHandler().get_queryset(workspace).exists()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "roles",
    [[[1]], ["x"], [[[], "VIEWER"]], [["1", "VIEWER"]], [[1, None]], {"a": 1}, "x"],
)
def test_malformed_exported_roles_are_ignored(
    enterprise_data_fixture, admin, settings, tmp_path, roles
):
    template = sync_template(enterprise_data_fixture, settings, tmp_path, [WRITE_TOOLS])
    path = tmp_path / "agent-kit.json"
    content = json.loads(path.read_text())
    for application in content["export"]:
        if application["type"] == "agent":
            application["run_as_identity_roles"] = roles
    path.write_text(json.dumps(content))
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    job = install(admin, workspace, template, create_identities=True)

    assert job.state == JOB_FINISHED, job.human_readable_error
    assert AgentApplication.objects.filter(workspace=workspace).exists()


@pytest.mark.django_db(transaction=True)
def test_an_identity_with_workspace_access_exports_no_roles(
    enterprise_data_fixture, admin
):
    source = enterprise_data_fixture.create_workspace(user=admin)
    database = enterprise_data_fixture.create_database_application(workspace=source)
    identity = enterprise_data_fixture.create_identity(
        workspace=source, role_uid="BUILDER"
    )
    RoleAssignmentHandler().assign_role(
        identity,
        source,
        role=Role.objects.get(uid="VIEWER"),
        scope=database.application_ptr,
    )
    agent = make_agent(enterprise_data_fixture, source, "Helper", WRITE_TOOLS, identity)

    (serialized,) = export_for_template([agent])

    # Without the key, an install falls back to the roles the tools need.
    assert "run_as_identity_roles" not in serialized


@pytest.mark.django_db(transaction=True)
def test_exported_identity_roles_need_permission_to_read_them(
    enterprise_data_fixture, admin
):
    builder = enterprise_data_fixture.create_user()
    source = enterprise_data_fixture.create_workspace(
        users=[admin], custom_permissions=[(builder, "BUILDER")]
    )
    database = enterprise_data_fixture.create_database_application(workspace=source)
    identity = enterprise_data_fixture.create_identity(
        workspace=source, role_uid="NO_ACCESS"
    )
    RoleAssignmentHandler().assign_role(
        identity,
        source,
        role=Role.objects.get(uid="VIEWER"),
        scope=database.application_ptr,
    )
    agent = make_agent(enterprise_data_fixture, source, "Helper", WRITE_TOOLS, identity)

    def export(user):
        config = ImportExportConfig(include_permission_data=False, exported_by=user)
        return agent.get_type().export_serialized(agent, config)

    assert export(admin)["run_as_identity_roles"] == [[database.id, "VIEWER"]]
    assert "run_as_identity_roles" not in export(builder)


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
def test_without_the_agent_builder_the_agent_keeps_waiting(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(enterprise_data_fixture, settings, tmp_path, [WRITE_TOOLS])
    workspace = enterprise_data_fixture.create_workspace(user=admin)
    settings.FEATURE_FLAGS = []

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
        "assign_role_batch",
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
        (Database.objects.get(workspace=workspace).id, "BUILDER")
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


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_a_user_template_install_recreates_the_template_identity_roles(
    enterprise_data_fixture, admin
):
    source = enterprise_data_fixture.create_workspace(user=admin)
    crm = enterprise_data_fixture.create_database_application(
        workspace=source, name="CRM"
    )
    ops = enterprise_data_fixture.create_database_application(
        workspace=source, name="Ops"
    )
    identity = enterprise_data_fixture.create_identity(
        workspace=source, name="Author", role_uid="NO_ACCESS"
    )
    RoleAssignmentHandler().assign_role_batch(
        source,
        [
            NewRoleAssignment(
                identity, Role.objects.get(uid="VIEWER"), crm.application_ptr
            )
        ],
    )
    # Tools that change data, so the fallback would give builder on both databases.
    agent = make_agent(enterprise_data_fixture, source, "Helper", WRITE_TOOLS, identity)
    copy = UserTemplateHandler().copy_applications(
        admin, [crm, ops, agent], name="Copy"
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
        (Database.objects.get(workspace=target, name="CRM").id, "VIEWER")
    }


@pytest.mark.django_db(transaction=True)
def test_exported_roles_that_cant_be_given_create_no_identity(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(enterprise_data_fixture, settings, tmp_path, [WRITE_TOOLS])
    path = tmp_path / "agent-kit.json"
    content = json.loads(path.read_text())
    database_id = next(
        application["id"]
        for application in content["export"]
        if application["type"] == "database"
    )
    for application in content["export"]:
        if application["type"] == "agent":
            application["run_as_identity_roles"] = [[database_id, "ADMIN"]]
    path.write_text(json.dumps(content))
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    job = install(admin, workspace, template, create_identities=True)

    assert job.state == JOB_FINISHED, job.human_readable_error
    agent = AgentApplication.objects.get(workspace=workspace)
    assert agent.run_as_subject_id is None
    assert agent.pending_tool_choices is not None
    assert not IdentityHandler().get_queryset(workspace).exists()


@pytest.mark.django_db(transaction=True)
def test_an_expected_identity_failure_is_logged_as_a_warning(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(enterprise_data_fixture, settings, tmp_path, [WRITE_TOOLS])
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    with (
        patch.object(
            IdentityService,
            "create_scoped_identity",
            side_effect=PermissionDenied(),
        ),
        patch("baserow.contrib.agent.service.logger") as logger,
    ):
        job = install(admin, workspace, template, create_identities=True)

    assert job.state == JOB_FINISHED
    assert logger.warning.called
    assert not logger.exception.called


@pytest.mark.django_db(transaction=True)
def test_an_identity_with_access_cant_be_scoped(enterprise_data_fixture, admin):
    workspace = enterprise_data_fixture.create_workspace(user=admin)
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    identity = enterprise_data_fixture.create_identity(
        workspace=workspace, role_uid="BUILDER"
    )

    with pytest.raises(IdentityCannotBeScoped):
        EnterpriseIdentityExtensionType().scope_to_applications(
            identity, [database], False, admin
        )


@pytest.mark.django_db(transaction=True)
def test_assigning_roles_without_role_permissions_still_checks_the_scopes(
    enterprise_data_fixture, admin
):
    workspace = enterprise_data_fixture.create_workspace(user=admin)
    other = enterprise_data_fixture.create_workspace(user=admin)
    elsewhere = enterprise_data_fixture.create_database_application(workspace=other)
    identity = enterprise_data_fixture.create_identity(
        workspace=workspace, role_uid="NO_ACCESS"
    )

    with pytest.raises(ScopeNotExist):
        action_type_registry.get_by_type(BatchAssignRoleActionType).do(
            admin,
            [
                NewRoleAssignment(
                    identity, Role.objects.get(uid="VIEWER"), elsewhere.application_ptr
                )
            ],
            workspace,
            check_role_permissions=False,
        )
    assert not RoleAssignment.objects.filter(subject_id=identity.id).exists()


@pytest.mark.django_db(transaction=True)
def test_the_roles_of_an_agent_waiting_for_an_identity_need_permission_to_read_them(
    enterprise_data_fixture, admin
):
    builder = enterprise_data_fixture.create_user()
    source = enterprise_data_fixture.create_workspace(
        users=[admin], custom_permissions=[(builder, "BUILDER")]
    )
    database = enterprise_data_fixture.create_database_application(workspace=source)
    agent = enterprise_data_fixture.create_agent_application(
        workspace=source, name="Helper"
    )
    agent.pending_tool_choices = {
        "allowed_tools": ["list_tables"],
        "identity_roles": [[database.id, "VIEWER"]],
    }
    agent.save(update_fields=["pending_tool_choices"])

    def export(user):
        config = ImportExportConfig(include_permission_data=False, exported_by=user)
        return agent.get_type().export_serialized(agent, config)

    assert export(None)["run_as_identity_roles"] == [[database.id, "VIEWER"]]
    assert export(admin)["run_as_identity_roles"] == [[database.id, "VIEWER"]]
    assert "run_as_identity_roles" not in export(builder)
