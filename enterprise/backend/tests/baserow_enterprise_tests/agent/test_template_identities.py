import json
from unittest.mock import ANY, MagicMock, patch
from zipfile import ZipFile

from django.core.management import call_command
from django.db import transaction
from django.urls import reverse

import pytest
from celery.exceptions import SoftTimeLimitExceeded
from rest_framework.status import HTTP_202_ACCEPTED

from baserow.contrib.agent.actions import UpdateAgentConfigurationActionType
from baserow.contrib.agent.api.serializers import AgentApplicationSerializer
from baserow.contrib.agent.application_types import AgentApplicationType
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import AgentApplication
from baserow.contrib.builder.models import Builder
from baserow.contrib.database.models import Database
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.actions import InstallTemplateActionType
from baserow.core.exceptions import PermissionDenied, PermissionException
from baserow.core.handler import CoreHandler
from baserow.core.identities.actions import CreateScopedIdentityActionType
from baserow.core.identities.exceptions import IdentityCannotBeScoped
from baserow.core.identities.handler import IdentityHandler
from baserow.core.identities.import_export import IdentityExport, imported_identity
from baserow.core.identities.service import IdentityService
from baserow.core.identities.signals import identity_deleted
from baserow.core.import_export.handler import MANIFEST_NAME, ImportExportHandler
from baserow.core.job_types import InstallTemplateJobType
from baserow.core.jobs.constants import JOB_FINISHED
from baserow.core.jobs.handler import JobHandler
from baserow.core.models import IdentityDefinition, Template, User
from baserow.core.registries import ImportExportConfig, application_type_registry
from baserow.core.snapshots.handler import SnapshotHandler
from baserow.core.storage import get_default_storage
from baserow.core.subjects import UserSubjectType
from baserow.core.trash.handler import TrashHandler
from baserow.core.user_templates.handler import UserTemplateHandler
from baserow.core.utils import Progress
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
WRITE_CHOICES = {
    "allowed_tools": ["list_tables", "create_rows"],
    "ask_first_tools": ["create_rows"],
}
# Stands for the id of the exported database in a parametrized role.
DATABASE = "<database>"


def export_for_template(applications, exported_by=None) -> tuple[list[dict], dict]:
    """The applications and what they hold beside them, as a template file does."""

    identity_export = IdentityExport()
    config = ImportExportConfig(
        include_permission_data=False,
        identity_export=identity_export,
        exported_by=exported_by,
    )
    serialized = [
        application.get_type().export_serialized(application, config)
        for application in applications
    ]
    workspace_objects = identity_export.serialize(
        exported_by, [application.id for application in applications]
    )
    return json.loads(json.dumps(serialized)), json.loads(json.dumps(workspace_objects))


def make_agent(fixture, workspace, name, tools, identity=None):
    agent = fixture.create_agent_application(
        workspace=workspace,
        name=name,
        instructions="Help.",
        provider_type="openai",
        model_identifier="test-model",
    )
    # With workspace access, it gets that role on each installed application.
    identity = identity or fixture.create_identity(
        workspace=workspace, name="Author", role_uid="BUILDER"
    )
    agent.run_as_subject_type, agent.run_as_subject_id = "auth.User", identity.id
    agent.save()
    allowed, ask_first = tools
    AgentHandler().set_allowed_tools(agent, allowed, ask_first_names=ask_first)
    return agent


def make_source(
    fixture,
    agents_tools,
    with_database=True,
    with_site=False,
    source_roles=None,
    workspace=None,
) -> list:
    """
    A database and an Agent for each tool choice, in a new workspace. With
    `source_roles`, the Agents act as one identity without workspace access that has
    those roles, by application name.
    """

    source = workspace or fixture.create_workspace()
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
    return [*applications, *agents]


def sync_applications(settings, tmp_path, applications, slug="agent-kit"):
    """The applications as an official template."""

    export, workspace_objects = export_for_template(applications)
    write_template(tmp_path, slug, export, workspace_objects)
    settings.APPLICATION_TEMPLATES_DIR = str(tmp_path)
    CoreHandler().sync_templates(pattern=slug)
    return Template.objects.get(slug=slug)


def sync_template(
    fixture, settings, tmp_path, agents_tools, slug="agent-kit", **kwargs
):
    """An official template of the applications of `make_source`."""

    return sync_applications(
        settings, tmp_path, make_source(fixture, agents_tools, **kwargs), slug
    )


def write_template(tmp_path, slug, export, workspace_objects=None) -> None:
    content = {
        "baserow_template_version": 1,
        "name": "Agent kit",
        "icon": "iconoir-shop",
        "keywords": [],
        "categories": ["Agents"],
        "export": export,
    }
    if workspace_objects is not None:
        content["workspace_objects"] = workspace_objects
    (tmp_path / f"{slug}.json").write_text(json.dumps(content))


def edit_template(tmp_path, change, slug="agent-kit") -> None:
    """Changes the template file after its sync, as an install reads it again."""

    path = tmp_path / f"{slug}.json"
    content = json.loads(path.read_text())
    change(content)
    path.write_text(json.dumps(content))


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


def install_waiting(user, workspace, template) -> list[AgentApplication]:
    """Installs as a user who may not create identities, so the Agents wait."""

    with patch.object(
        IdentityService, "can_create_scoped_identity", return_value=False
    ):
        job = install(user, workspace, template)
    assert job.state == JOB_FINISHED, job.human_readable_error
    return list(AgentApplication.objects.filter(workspace=workspace).order_by("name"))


def manifest_of(export_path) -> dict:
    with (
        get_default_storage().open(export_path, "rb") as archive,
        ZipFile(archive) as zip_file,
    ):
        return json.loads(zip_file.read(MANIFEST_NAME))


def import_zip(user, workspace, export_path, application_ids=None):
    handler = ImportExportHandler()
    with get_default_storage().open(export_path, "rb") as archive:
        resource = handler.create_resource_from_file(user, "export.zip", archive)
    return handler.import_workspace_applications(
        user, workspace, resource, application_ids=application_ids
    )


def database_referring_to(fixture, workspace, user):
    """A database whose row, collaborator field, view and filters refer to the user."""

    database = fixture.create_database_application(workspace=workspace, name="CRM")
    table = fixture.create_database_table(database=database)
    fixture.create_text_field(table=table, name="Name", primary=True)
    created_by = fixture.create_created_by_field(table=table, name="Created by")
    fixture.create_last_modified_by_field(table=table, name="Modified by")
    people = fixture.create_multiple_collaborators_field(
        table=table, name="People", include_identities=True
    )
    RowHandler().force_create_row(user, table, {people.db_column: [{"id": user.id}]})
    view = fixture.create_grid_view(table=table, owned_by=user)
    fixture.create_view_filter(
        view=view, field=created_by, type="user_is", value=str(user.id)
    )
    fixture.create_view_filter(
        view=view, field=people, type="multiple_collaborators_has", value=str(user.id)
    )
    return database


def references_of(database) -> dict:
    """The users the data made by `database_referring_to` refers to."""

    table = database.table_set.get()
    row = table.get_model().objects.get()
    people = table.field_set.get(name="People")
    view = table.view_set.get()
    return {
        "created_by": row.created_by_id,
        "last_modified_by": row.last_modified_by_id,
        "collaborators": [user.id for user in getattr(row, people.db_column).all()],
        "view_owner": view.owned_by_id,
        "filters": set(view.viewfilter_set.values_list("value", flat=True)),
    }


def referring_to(identity) -> dict:
    return {
        "created_by": identity.id,
        "last_modified_by": identity.id,
        "collaborators": [identity.id],
        "view_owner": identity.id,
        "filters": {str(identity.id)},
    }


def role_on(application, role_uid) -> dict:
    return {
        "scope_type": "application",
        "scope_id": application.id,
        "role": role_uid,
    }


def workspace_role(role_uid) -> dict:
    return {"scope_type": "workspace", "role": role_uid}


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


def assert_waits(agent, with_definition=True) -> None:
    agent.refresh_from_db()
    assert agent.run_as_subject_id is None
    assert agent.pending_tool_choices is not None
    assert (agent.identity_definition_id is not None) == with_definition


def pick_identity(user, agent, identity) -> None:
    action_type_registry.get_by_type(UpdateAgentConfigurationActionType).do(
        user,
        agent.id,
        run_as_subject_type=UserSubjectType.type,
        run_as_subject_id=identity.id,
    )


def trash(user, agent) -> None:
    with transaction.atomic():
        TrashHandler.trash(user, agent.workspace, agent, agent)


def permanently_delete(agent) -> None:
    with transaction.atomic():
        TrashHandler.permanently_delete(agent)


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

    job = install(admin, workspace, template)

    assert job.state == JOB_FINISHED, job.human_readable_error
    agent = AgentApplication.objects.get(workspace=workspace)
    database = Database.objects.get(workspace=workspace, name="CRM")
    site = Builder.objects.get(workspace=workspace, name="Site")
    identity = run_identity(agent)
    # The name of the template's identity, not of the Agent.
    assert identity.first_name == "Author"
    assert IdentityHandler.get_role_uid(identity) == "NO_ACCESS"
    # Not on the Agent itself, so it can't change its own configuration.
    assert roles_of(identity) == {(database.id, "BUILDER"), (site.id, "BUILDER")}
    assert other_database.id not in {scope for scope, _ in roles_of(identity)}
    assert AgentHandler().get_tool_configuration(agent) == WRITE_CHOICES
    assert agent.pending_tool_choices is None
    # Nothing waits for the identity any more.
    assert agent.identity_definition_id is None
    assert not IdentityDefinition.objects.filter(workspace=workspace).exists()
    # Creating, scoping and binding the identity are all audited.
    assert set(
        AuditLogEntry.objects.filter(workspace_id=workspace.id).values_list(
            "action_type", flat=True
        )
    ) >= {
        CreateScopedIdentityActionType.type,
        BatchAssignRoleActionType.type,
        UpdateAgentConfigurationActionType.type,
    }


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("role_uid", ["VIEWER", "COMMENTER", "EDITOR", "BUILDER"])
def test_an_identity_with_workspace_access_gets_its_role_on_each_application(
    enterprise_data_fixture, admin, settings, tmp_path, role_uid
):
    source = enterprise_data_fixture.create_workspace()
    database = enterprise_data_fixture.create_database_application(
        workspace=source, name="CRM"
    )
    site = enterprise_data_fixture.create_builder_application(
        workspace=source, name="Site"
    )
    author = enterprise_data_fixture.create_identity(
        workspace=source, name="Author", role_uid=role_uid
    )
    # Tools that change data don't make it a builder.
    agent = make_agent(enterprise_data_fixture, source, "Helper", WRITE_TOOLS, author)
    template = sync_applications(settings, tmp_path, [database, site, agent])
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    install(admin, workspace, template)

    identity = run_identity(AgentApplication.objects.get(workspace=workspace))
    assert IdentityHandler.get_role_uid(identity) == "NO_ACCESS"
    assert roles_of(identity) == {
        (Database.objects.get(workspace=workspace).id, role_uid),
        (Builder.objects.get(workspace=workspace).id, role_uid),
    }


@pytest.mark.django_db(transaction=True)
def test_the_roles_of_an_identity_with_workspace_access_on_single_applications_win(
    enterprise_data_fixture, admin, settings, tmp_path
):
    source = enterprise_data_fixture.create_workspace()
    crm, ops, hidden = [
        enterprise_data_fixture.create_database_application(workspace=source, name=name)
        for name in ("CRM", "Ops", "Hidden")
    ]
    author = enterprise_data_fixture.create_identity(
        workspace=source, name="Author", role_uid="BUILDER"
    )
    for scope, uid in ((crm, "VIEWER"), (hidden, "NO_ACCESS")):
        RoleAssignmentHandler().assign_role(
            author, source, role=Role.objects.get(uid=uid), scope=scope.application_ptr
        )
    agent = make_agent(enterprise_data_fixture, source, "Helper", WRITE_TOOLS, author)
    template = sync_applications(settings, tmp_path, [crm, ops, hidden, agent])
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    install(admin, workspace, template)

    identity = run_identity(AgentApplication.objects.get(workspace=workspace))
    # Builder only where it had no role of its own, and nothing on the hidden one.
    assert roles_of(identity) == {
        (Database.objects.get(workspace=workspace, name="CRM").id, "VIEWER"),
        (Database.objects.get(workspace=workspace, name="Ops").id, "BUILDER"),
    }


@pytest.mark.django_db(transaction=True)
def test_an_agent_only_template_creates_an_identity_without_access(
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

    job = install(admin, workspace, template)

    assert job.state == JOB_FINISHED, job.human_readable_error
    agent = AgentApplication.objects.get(workspace=workspace)
    identity = run_identity(agent)
    # Its tools are checked against no access when they run.
    assert IdentityHandler.get_role_uid(identity) == "NO_ACCESS"
    assert roles_of(identity) == set()
    assert agent.pending_tool_choices is None


@pytest.mark.django_db(transaction=True)
def test_a_builder_install_creates_identities(
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

    job = install(builder, workspace, template)

    assert job.state == JOB_FINISHED, job.human_readable_error
    agent = AgentApplication.objects.get(workspace=workspace)
    identity = run_identity(agent)
    assert IdentityHandler.get_role_uid(identity) == "NO_ACCESS"
    assert roles_of(identity) == {
        (Database.objects.get(workspace=workspace).id, "BUILDER")
    }
    assert agent.pending_tool_choices is None


@pytest.mark.django_db(transaction=True)
def test_an_installer_without_the_permission_leaves_the_agent_waiting(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(
        enterprise_data_fixture,
        settings,
        tmp_path,
        [WRITE_TOOLS],
        source_roles={"CRM": "VIEWER"},
    )
    builder = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(
        users=[admin], custom_permissions=[(builder, "BUILDER")]
    )

    (agent,) = install_waiting(builder, workspace, template)

    assert_waits(agent)
    assert agent.pending_tool_choices == WRITE_CHOICES
    assert not IdentityHandler().get_queryset(workspace).exists()
    # What the identity would be is kept, with its roles by the new ids.
    definition = IdentityDefinition.objects.get(workspace=workspace)
    assert agent.identity_definition_id == definition.id
    assert definition.name == "Author"
    assert definition.roles == [
        workspace_role("NO_ACCESS"),
        role_on(Database.objects.get(workspace=workspace), "VIEWER"),
    ]


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

    identity = IdentityService().create_scoped_identity(
        builder, workspace, name="Helper"
    )

    with pytest.raises(PermissionException):
        IdentityService().scope_identity(
            builder, identity, [hidden], [(hidden.id, "VIEWER")]
        )

    assert roles_of(identity) == set()


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

    install(admin, workspace, template)

    identity = run_identity(AgentApplication.objects.get(workspace=workspace))
    assert IdentityHandler.get_role_uid(identity) == "NO_ACCESS"
    assert roles_of(identity) == {
        (Database.objects.get(workspace=workspace).id, "VIEWER")
    }


@pytest.mark.django_db(transaction=True)
def test_an_admin_role_is_recreated_for_an_installer_who_can_change_roles(
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

    install(admin, workspace, template)

    identity = run_identity(AgentApplication.objects.get(workspace=workspace))
    assert roles_of(identity) == {
        (Database.objects.get(workspace=workspace).id, "ADMIN"),
        (Builder.objects.get(workspace=workspace).id, "VIEWER"),
    }


@pytest.mark.django_db(transaction=True)
def test_an_admin_role_is_a_builder_role_for_an_installer_who_cant_change_roles(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(
        enterprise_data_fixture,
        settings,
        tmp_path,
        [WRITE_TOOLS],
        source_roles={"CRM": "ADMIN"},
    )
    builder = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(
        users=[admin], custom_permissions=[(builder, "BUILDER")]
    )

    job = install(builder, workspace, template)

    assert job.state == JOB_FINISHED, job.human_readable_error
    identity = run_identity(AgentApplication.objects.get(workspace=workspace))
    assert roles_of(identity) == {
        (Database.objects.get(workspace=workspace).id, "BUILDER")
    }


@pytest.mark.django_db(transaction=True)
def test_editor_and_commenter_roles_are_recreated(
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

    install(admin, workspace, template)

    identity = run_identity(AgentApplication.objects.get(workspace=workspace))
    assert roles_of(identity) == {
        (Database.objects.get(workspace=workspace).id, "EDITOR"),
        (Builder.objects.get(workspace=workspace).id, "COMMENTER"),
    }


@pytest.mark.django_db(transaction=True)
def test_roles_land_when_the_agent_is_imported_before_the_database(
    enterprise_data_fixture, admin, settings, tmp_path
):
    database, agent = make_source(
        enterprise_data_fixture, [WRITE_TOOLS], source_roles={"CRM": "EDITOR"}
    )
    template = sync_applications(settings, tmp_path, [agent, database])
    workspace = enterprise_data_fixture.create_workspace(user=admin)
    imported = []
    agent_type = agent.get_type()
    import_agent = agent_type.import_serialized

    def record_order(*args, **kwargs):
        imported.append(Database.objects.filter(workspace=workspace).exists())
        return import_agent(*args, **kwargs)

    # Listed first isn't enough: applications are imported by priority.
    with (
        patch.object(agent_type, "import_application_priority", 100),
        patch.object(agent_type, "import_serialized", record_order),
    ):
        job = install(admin, workspace, template)

    assert job.state == JOB_FINISHED, job.human_readable_error
    # The database didn't exist yet when the Agent was imported.
    assert imported == [False]
    identity = run_identity(AgentApplication.objects.get(workspace=workspace))
    assert roles_of(identity) == {
        (Database.objects.get(workspace=workspace).id, "EDITOR")
    }


@pytest.mark.django_db(transaction=True)
def test_an_identity_without_application_roles_gets_no_access(
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

    job = install(admin, workspace, template)

    assert job.state == JOB_FINISHED, job.human_readable_error
    identity = run_identity(AgentApplication.objects.get(workspace=workspace))
    assert IdentityHandler.get_role_uid(identity) == "NO_ACCESS"
    assert roles_of(identity) == set()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "workspace_objects",
    ["x", ["x"], {"identities": "x"}, {"identities": ["x", 1, None]}],
)
def test_a_malformed_identities_section_is_ignored(
    enterprise_data_fixture, admin, settings, tmp_path, workspace_objects
):
    template = sync_template(enterprise_data_fixture, settings, tmp_path, [WRITE_TOOLS])
    edit_template(
        tmp_path,
        lambda content: content.update(workspace_objects=workspace_objects),
    )
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    job = install(admin, workspace, template)

    assert job.state == JOB_FINISHED, job.human_readable_error
    assert Database.objects.filter(workspace=workspace).exists()
    assert_waits(
        AgentApplication.objects.get(workspace=workspace), with_definition=False
    )
    assert not IdentityHandler().get_queryset(workspace).exists()
    assert not IdentityDefinition.objects.filter(workspace=workspace).exists()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "values",
    [
        {"key": 1},
        {"key": ""},
        {"key": None},
        {"name": None},
        {"name": "  "},
        {"name": ["Author"]},
        {"name": "Auth\x00r"},
        # Nothing that is installed refers to it.
        {"key": "another"},
    ],
)
def test_a_malformed_exported_identity_is_ignored(
    enterprise_data_fixture, admin, settings, tmp_path, values
):
    template = sync_template(enterprise_data_fixture, settings, tmp_path, [WRITE_TOOLS])
    edit_template(
        tmp_path,
        lambda content: content["workspace_objects"]["identities"][0].update(values),
    )
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    job = install(admin, workspace, template)

    assert job.state == JOB_FINISHED, job.human_readable_error
    assert_waits(
        AgentApplication.objects.get(workspace=workspace), with_definition=False
    )
    assert not IdentityHandler().get_queryset(workspace).exists()
    assert not IdentityDefinition.objects.filter(workspace=workspace).exists()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "roles,expected_role",
    [
        # Roles that can't be read give no access.
        (None, None),
        ("x", None),
        ({"a": 1}, None),
        (["x", [1, "VIEWER"]], None),
        ([{"scope_type": "table", "scope_id": DATABASE, "role": "VIEWER"}], None),
        ([{"scope_id": DATABASE, "role": "VIEWER"}], None),
        ([{"scope_type": "application", "scope_id": [], "role": "VIEWER"}], None),
        ([{"scope_type": "application", "scope_id": "1", "role": "VIEWER"}], None),
        ([{"scope_type": "application", "scope_id": True, "role": "VIEWER"}], None),
        ([{"scope_type": "application", "scope_id": DATABASE, "role": None}], None),
        ([{"scope_type": "application", "role": "VIEWER"}], None),
        # Neither do roles that can't be given, or on what isn't installed.
        (
            [{"scope_type": "application", "scope_id": DATABASE, "role": "NO_ROLE"}],
            None,
        ),
        ([{"scope_type": "application", "scope_id": 999999, "role": "VIEWER"}], None),
        ([{"scope_type": "workspace", "role": "NO_ROLE"}], None),
        ([{"scope_type": "workspace", "role": ["EDITOR"]}], None),
        # What can be read is kept.
        (
            [
                "x",
                {"scope_type": "application", "scope_id": DATABASE, "role": "VIEWER"},
            ],
            "VIEWER",
        ),
        # The role on the workspace is given on the application.
        ([{"scope_type": "workspace", "role": "EDITOR"}], "EDITOR"),
        # A member of a workspace without roles can change its applications.
        ([{"scope_type": "workspace", "role": "MEMBER"}], "BUILDER"),
        # Only the first role on the workspace counts.
        (
            [
                {"scope_type": "workspace", "role": "VIEWER"},
                {"scope_type": "workspace", "role": "ADMIN"},
            ],
            "VIEWER",
        ),
        # Unless the application has its own, also one that gives no access.
        (
            [
                {"scope_type": "workspace", "role": "BUILDER"},
                {"scope_type": "application", "scope_id": DATABASE, "role": "VIEWER"},
            ],
            "VIEWER",
        ),
        (
            [
                {"scope_type": "workspace", "role": "BUILDER"},
                {
                    "scope_type": "application",
                    "scope_id": DATABASE,
                    "role": "NO_ACCESS",
                },
            ],
            None,
        ),
    ],
)
def test_malformed_exported_roles_are_left_out(
    enterprise_data_fixture, admin, settings, tmp_path, roles, expected_role
):
    template = sync_template(enterprise_data_fixture, settings, tmp_path, [WRITE_TOOLS])

    def change(content):
        database_id = next(
            application["id"]
            for application in content["export"]
            if application["type"] == "database"
        )
        for role in roles if isinstance(roles, list) else []:
            if isinstance(role, dict) and role.get("scope_id") == DATABASE:
                role["scope_id"] = database_id
        content["workspace_objects"]["identities"][0]["roles"] = roles

    edit_template(tmp_path, change)
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    job = install(admin, workspace, template)

    assert job.state == JOB_FINISHED, job.human_readable_error
    database = Database.objects.get(workspace=workspace)
    identity = run_identity(AgentApplication.objects.get(workspace=workspace))
    assert roles_of(identity) == (
        {(database.id, expected_role)} if expected_role else set()
    )


@pytest.mark.django_db(transaction=True)
def test_an_old_template_file_installs_with_the_agent_waiting(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(enterprise_data_fixture, settings, tmp_path, [WRITE_TOOLS])

    def as_before(content):
        del content["workspace_objects"]
        for application in content["export"]:
            if application["type"] == "agent":
                del application["run_as_identity_key"]
                application["run_as_identity"] = {
                    "key": "author",
                    "application_roles": None,
                }

    edit_template(tmp_path, as_before)
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    job = install(admin, workspace, template)

    assert job.state == JOB_FINISHED, job.human_readable_error
    assert Database.objects.filter(workspace=workspace).exists()
    agent = AgentApplication.objects.get(workspace=workspace)
    assert_waits(agent, with_definition=False)
    assert agent.pending_tool_choices == WRITE_CHOICES
    assert not IdentityHandler().get_queryset(workspace).exists()
    assert not IdentityDefinition.objects.filter(workspace=workspace).exists()


@pytest.mark.django_db(transaction=True)
def test_an_identity_is_exported_once_beside_the_applications(
    enterprise_data_fixture, admin
):
    source = enterprise_data_fixture.create_workspace(user=admin)
    database = enterprise_data_fixture.create_database_application(workspace=source)
    identity = enterprise_data_fixture.create_identity(
        workspace=source, name="Author", role_uid="BUILDER"
    )
    RoleAssignmentHandler().assign_role(
        identity,
        source,
        role=Role.objects.get(uid="VIEWER"),
        scope=database.application_ptr,
    )
    agent = make_agent(enterprise_data_fixture, source, "Helper", WRITE_TOOLS, identity)

    (_, serialized), workspace_objects = export_for_template([database, agent])

    assert workspace_objects == {
        "identities": [
            {
                "key": serialized["run_as_identity_key"],
                "name": "Author",
                "email": identity.email,
                "roles": [workspace_role("BUILDER"), role_on(database, "VIEWER")],
            }
        ]
    }
    # The Agent only holds the key.
    assert "run_as_identity" not in serialized
    assert "identity" not in (serialized.get("pending_tool_choices") or {})


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

    def exported_roles(user):
        _, workspace_objects = export_for_template([database, agent], user)
        return workspace_objects["identities"][0]["roles"]

    assert exported_roles(admin) == [
        workspace_role("NO_ACCESS"),
        role_on(database, "VIEWER"),
    ]
    # Hidden, and exported as no access so an install gives none there.
    assert exported_roles(builder) == [
        workspace_role("NO_ACCESS"),
        role_on(database, "NO_ACCESS"),
        role_on(agent, "NO_ACCESS"),
    ]


@pytest.mark.django_db(transaction=True)
def test_roles_on_applications_that_arent_exported_are_left_out(
    enterprise_data_fixture, admin
):
    database, agent = make_source(
        enterprise_data_fixture, [WRITE_TOOLS], source_roles={"CRM": "VIEWER"}
    )

    _, workspace_objects = export_for_template([agent])

    assert workspace_objects["identities"][0]["roles"] == [workspace_role("NO_ACCESS")]


@pytest.mark.django_db(transaction=True)
def test_an_application_with_table_roles_isnt_exported(enterprise_data_fixture, admin):
    source = enterprise_data_fixture.create_workspace(user=admin)
    crm = enterprise_data_fixture.create_database_application(workspace=source)
    ops = enterprise_data_fixture.create_database_application(workspace=source)
    salaries = enterprise_data_fixture.create_database_table(database=crm)
    identity = enterprise_data_fixture.create_identity(
        workspace=source, role_uid="NO_ACCESS"
    )
    handler = RoleAssignmentHandler()
    for scope in (crm.application_ptr, ops.application_ptr):
        handler.assign_role(
            identity, source, role=Role.objects.get(uid="EDITOR"), scope=scope
        )
    handler.assign_role(
        identity, source, role=Role.objects.get(uid="NO_ACCESS"), scope=salaries
    )
    agent = make_agent(enterprise_data_fixture, source, "Helper", WRITE_TOOLS, identity)

    _, workspace_objects = export_for_template([crm, ops, agent])

    # Editor on all of the CRM would reach the table the identity can't.
    assert workspace_objects["identities"][0]["roles"] == [
        workspace_role("NO_ACCESS"),
        role_on(crm, "NO_ACCESS"),
        role_on(ops, "EDITOR"),
    ]


@pytest.mark.django_db(transaction=True)
def test_an_application_a_team_of_the_identity_has_a_say_on_isnt_exported(
    enterprise_data_fixture, admin
):
    source = enterprise_data_fixture.create_workspace(user=admin)
    crm, ops, wiki, docs = [
        enterprise_data_fixture.create_database_application(workspace=source)
        for _ in range(4)
    ]
    salaries = enterprise_data_fixture.create_database_table(database=crm)
    identity = enterprise_data_fixture.create_identity(
        workspace=source, role_uid="BUILDER"
    )
    team = enterprise_data_fixture.create_team(workspace=source, members=[identity])
    handler = RoleAssignmentHandler()
    for scope in (crm.application_ptr, ops.application_ptr):
        handler.assign_role(
            identity, source, role=Role.objects.get(uid="EDITOR"), scope=scope
        )
    # On a table of an application, on one where the identity has its own role,
    # and on one where it has none.
    for scope in (salaries, ops.application_ptr, wiki.application_ptr):
        handler.assign_role(
            team, source, role=Role.objects.get(uid="VIEWER"), scope=scope
        )
    agent = make_agent(enterprise_data_fixture, source, "Helper", WRITE_TOOLS, identity)

    _, workspace_objects = export_for_template([crm, ops, wiki, docs, agent])

    assert workspace_objects["identities"][0]["roles"] == [
        workspace_role("BUILDER"),
        # The team only views a table of it.
        role_on(crm, "NO_ACCESS"),
        # Its own role counts before the team's.
        role_on(ops, "EDITOR"),
        # The team narrows the role on the workspace.
        role_on(wiki, "NO_ACCESS"),
    ]


@pytest.mark.django_db(transaction=True)
def test_without_rbac_the_agent_waits_for_an_identity(
    enterprise_data_fixture, synced_roles, settings, tmp_path
):
    # No enterprise license, so an identity could only be a workspace member.
    template = sync_template(enterprise_data_fixture, settings, tmp_path, [WRITE_TOOLS])
    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    assert not IdentityService().can_create_scoped_identity(user, workspace)

    job = install(user, workspace, template)

    assert job.state == JOB_FINISHED, job.human_readable_error
    assert_waits(AgentApplication.objects.get(workspace=workspace))
    assert not IdentityHandler().get_queryset(workspace).exists()


@pytest.mark.django_db(transaction=True)
def test_without_the_agent_builder_the_agent_keeps_waiting(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(enterprise_data_fixture, settings, tmp_path, [WRITE_TOOLS])
    workspace = enterprise_data_fixture.create_workspace(user=admin)
    settings.FEATURE_FLAGS = []

    job = install(admin, workspace, template)

    assert job.state == JOB_FINISHED
    assert_waits(
        AgentApplication.objects.get(workspace=workspace), with_definition=False
    )
    assert not IdentityHandler().get_queryset(workspace).exists()


@pytest.mark.django_db(transaction=True)
def test_a_failed_role_assignment_leaves_the_identity_without_access(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(enterprise_data_fixture, settings, tmp_path, [WRITE_TOOLS])
    workspace = enterprise_data_fixture.create_workspace(user=admin)
    error = Role.DoesNotExist("boom")

    with (
        patch.object(RoleAssignmentHandler, "assign_role_batch", side_effect=error),
        patch("baserow.core.identities.import_export.exception_capturer") as capturer,
    ):
        job = install(admin, workspace, template)

    assert job.state == JOB_FINISHED
    capturer.assert_called_once_with(error)
    assert Database.objects.filter(workspace=workspace).exists()
    # The Agent acts as it, and whoever manages identities gives it its access.
    identity = run_identity(AgentApplication.objects.get(workspace=workspace))
    assert roles_of(identity) == set()


@pytest.mark.django_db(transaction=True)
def test_an_agent_without_tools_gets_its_identity_too(
    enterprise_data_fixture, admin, settings, tmp_path
):
    # Its triggers need the identity as much as tools do.
    template = sync_template(
        enterprise_data_fixture,
        settings,
        tmp_path,
        [([], [])],
        source_roles={"CRM": "EDITOR"},
    )
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    job = install(admin, workspace, template)

    assert job.state == JOB_FINISHED, job.human_readable_error
    agent = AgentApplication.objects.get(workspace=workspace)
    assert roles_of(run_identity(agent)) == {
        (Database.objects.get(workspace=workspace).id, "EDITOR")
    }
    assert agent.pending_tool_choices is None
    assert not IdentityDefinition.objects.filter(workspace=workspace).exists()


@pytest.mark.django_db(transaction=True)
def test_an_agent_without_tools_waits_for_its_identity_too(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(
        enterprise_data_fixture,
        settings,
        tmp_path,
        [([], [])],
        source_roles={"CRM": "EDITOR"},
    )
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    (agent,) = install_waiting(admin, workspace, template)

    assert agent.run_as_subject_id is None
    assert agent.identity_definition_id is not None
    # A template saved from it carries the identity on.
    (serialized,), workspace_objects = export_for_template([agent])
    assert [identity["key"] for identity in workspace_objects["identities"]] == [
        serialized["run_as_identity_key"]
    ]


@pytest.mark.django_db(transaction=True)
def test_the_install_endpoint_creates_identities(
    enterprise_data_fixture, admin, settings, tmp_path, api_client
):
    template = sync_template(enterprise_data_fixture, settings, tmp_path, [WRITE_TOOLS])
    workspace = enterprise_data_fixture.create_workspace(user=admin)
    token = enterprise_data_fixture.generate_token(admin)
    url = reverse(
        "api:templates:install_async",
        kwargs={"workspace_id": workspace.id, "template_id": template.id},
    )

    response = api_client.post(url, HTTP_AUTHORIZATION=f"JWT {token}")

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
    # The template holds what the identity would be, not an identity.
    assert IdentityDefinition.objects.filter(workspace=copy).count() == 1
    assert not IdentityHandler().get_queryset(copy).exists()
    assert_waits(AgentApplication.objects.get(workspace=copy))
    revision = enterprise_data_fixture.create_user_template(user=admin, workspace=copy)
    content = UserTemplateHandler().serialize_template_content(revision)
    target = enterprise_data_fixture.create_workspace(user=admin)

    with transaction.atomic():
        action_type_registry.get_by_type(InstallTemplateActionType).do(
            admin, target, revision, content=content
        )

    installed = AgentApplication.objects.get(workspace=target)
    identity = run_identity(installed)
    assert identity.first_name == "Author"
    assert roles_of(identity) == {
        (Database.objects.get(workspace=target).id, "BUILDER")
    }
    assert installed.pending_tool_choices is None
    assert not IdentityDefinition.objects.filter(workspace=target).exists()
    # The template keeps its own, for the next install.
    assert IdentityDefinition.objects.filter(workspace=copy).count() == 1


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
    # Tools that change data don't give it more than it had.
    agent = make_agent(enterprise_data_fixture, source, "Helper", WRITE_TOOLS, identity)
    copy = UserTemplateHandler().copy_applications(
        admin, [crm, ops, agent], name="Copy"
    )
    revision = enterprise_data_fixture.create_user_template(user=admin, workspace=copy)
    content = UserTemplateHandler().serialize_template_content(revision)
    target = enterprise_data_fixture.create_workspace(user=admin)

    with transaction.atomic():
        action_type_registry.get_by_type(InstallTemplateActionType).do(
            admin, target, revision, content=content
        )

    installed = AgentApplication.objects.get(workspace=target)
    assert roles_of(run_identity(installed)) == {
        (Database.objects.get(workspace=target, name="CRM").id, "VIEWER")
    }


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "email",
    [f"{'a' * 300}@identities.invalid", "a\x00b@identities.invalid", 1, ["x"]],
)
def test_an_address_that_cant_be_stored_is_left_out(
    enterprise_data_fixture, admin, settings, tmp_path, email
):
    template = sync_template(enterprise_data_fixture, settings, tmp_path, [WRITE_TOOLS])
    edit_template(
        tmp_path,
        lambda content: content["workspace_objects"]["identities"][0].update(
            email=email
        ),
    )
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    (agent,) = install_waiting(admin, workspace, template)

    assert_waits(agent)
    assert IdentityDefinition.objects.get(workspace=workspace).source_email is None


@pytest.mark.django_db(transaction=True)
def test_an_identity_named_like_a_link_isnt_created(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(enterprise_data_fixture, settings, tmp_path, [WRITE_TOOLS])
    edit_template(
        tmp_path,
        lambda content: content["workspace_objects"]["identities"][0].update(
            name="Reset your password at evil-login.com"
        ),
    )
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    job = install(admin, workspace, template)

    assert job.state == JOB_FINISHED, job.human_readable_error
    assert_waits(AgentApplication.objects.get(workspace=workspace))
    assert not IdentityHandler().get_queryset(workspace).exists()


@pytest.mark.django_db(transaction=True)
def test_a_taken_identity_name_gets_a_suffix(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(enterprise_data_fixture, settings, tmp_path, [READ_TOOLS])
    workspace = enterprise_data_fixture.create_workspace(user=admin)
    taken = enterprise_data_fixture.create_identity(workspace=workspace, name="Author")

    install(admin, workspace, template)

    identity = run_identity(AgentApplication.objects.get(workspace=workspace))
    assert identity.id != taken.id
    assert identity.first_name == "Author 2"


@pytest.mark.django_db(transaction=True)
def test_an_unexpected_identity_failure_is_reported(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(enterprise_data_fixture, settings, tmp_path, [WRITE_TOOLS])
    workspace = enterprise_data_fixture.create_workspace(user=admin)
    error = RuntimeError("boom")

    with (
        patch.object(IdentityService, "create_scoped_identity", side_effect=error),
        patch("baserow.core.identities.import_export.exception_capturer") as capturer,
    ):
        job = install(admin, workspace, template)

    assert job.state == JOB_FINISHED
    capturer.assert_called_once_with(error)
    assert_waits(AgentApplication.objects.get(workspace=workspace))


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("method", ["create_scoped_identity", "scope_identity"])
def test_the_time_limit_isnt_caught_while_creating_an_identity(
    enterprise_data_fixture, admin, settings, tmp_path, method
):
    template = sync_template(enterprise_data_fixture, settings, tmp_path, [WRITE_TOOLS])
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    with (
        patch.object(IdentityService, method, side_effect=SoftTimeLimitExceeded()),
        pytest.raises(SoftTimeLimitExceeded),
        transaction.atomic(),
    ):
        CoreHandler().install_template(admin, workspace, template)


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
        patch("baserow.core.identities.import_export.logger") as logger,
    ):
        job = install(admin, workspace, template)

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
            identity, [database], admin, [(database.id, "VIEWER")]
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
    viewer = [{"scope_type": "application", "scope_id": database.id, "role": "VIEWER"}]
    agent = enterprise_data_fixture.create_agent_application(
        workspace=source,
        name="Helper",
        pending_tool_choices={"allowed_tools": ["list_tables"]},
        identity_definition=IdentityDefinition.objects.create(
            workspace=source, name="Waiting", roles=viewer
        ),
    )

    def exported(user):
        _, workspace_objects = export_for_template([database, agent], user)
        (identity,) = workspace_objects["identities"]
        return identity

    assert exported(None) == {
        "key": ANY,
        "name": "Waiting",
        "email": None,
        "roles": viewer,
    }
    assert exported(admin)["roles"] == viewer
    # Hidden, and exported as no access so an install gives none there.
    assert exported(builder)["roles"] == [
        role_on(database, "NO_ACCESS"),
        role_on(agent, "NO_ACCESS"),
    ]


@pytest.mark.django_db(transaction=True)
def test_agents_of_the_same_identity_share_one_new_identity(
    enterprise_data_fixture, admin, settings, tmp_path
):
    # One reads and one writes, as the same identity that only views the database.
    template = sync_template(
        enterprise_data_fixture,
        settings,
        tmp_path,
        [READ_TOOLS, WRITE_TOOLS],
        source_roles={"CRM": "VIEWER"},
    )
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    job = install(admin, workspace, template)

    assert job.state == JOB_FINISHED, job.human_readable_error
    first, second = AgentApplication.objects.filter(workspace=workspace).order_by(
        "name"
    )
    identity = run_identity(first)
    assert run_identity(second).id == identity.id
    assert identity.first_name == "Author"
    assert IdentityHandler().get_queryset(workspace).count() == 1
    assert roles_of(identity) == {
        (Database.objects.get(workspace=workspace).id, "VIEWER")
    }
    assert first.pending_tool_choices is None
    assert second.pending_tool_choices is None
    assert not IdentityDefinition.objects.filter(workspace=workspace).exists()


@pytest.mark.django_db(transaction=True)
def test_agents_sharing_an_identity_with_workspace_access_share_one_too(
    enterprise_data_fixture, admin, settings, tmp_path
):
    source = enterprise_data_fixture.create_workspace()
    database = enterprise_data_fixture.create_database_application(
        workspace=source, name="CRM"
    )
    author = enterprise_data_fixture.create_identity(
        workspace=source, name="Author", role_uid="BUILDER"
    )
    agents = [
        make_agent(enterprise_data_fixture, source, name, tools, author)
        for name, tools in (("Reader", READ_TOOLS), ("Writer", WRITE_TOOLS))
    ]
    template = sync_applications(settings, tmp_path, [database, *agents])
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    install(admin, workspace, template)

    reader, writer = AgentApplication.objects.filter(workspace=workspace).order_by(
        "name"
    )
    identity = run_identity(reader)
    assert run_identity(writer).id == identity.id
    assert roles_of(identity) == {
        (Database.objects.get(workspace=workspace).id, "BUILDER")
    }


@pytest.mark.django_db(transaction=True)
def test_installs_of_the_same_template_dont_share_an_identity(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(
        enterprise_data_fixture,
        settings,
        tmp_path,
        [READ_TOOLS],
        source_roles={"CRM": "VIEWER"},
    )
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    install(admin, workspace, template)
    install(admin, workspace, template)

    first, second = AgentApplication.objects.filter(workspace=workspace).order_by("id")
    first_database, second_database = Database.objects.filter(
        workspace=workspace
    ).order_by("id")
    first_identity, second_identity = run_identity(first), run_identity(second)
    assert first_identity.id != second_identity.id
    assert first_identity.first_name == "Author"
    assert second_identity.first_name == "Author 2"
    # Neither Agent gets the access of the other install.
    assert roles_of(first_identity) == {(first_database.id, "VIEWER")}
    assert roles_of(second_identity) == {(second_database.id, "VIEWER")}


@pytest.mark.django_db(transaction=True)
def test_waiting_installs_of_the_same_template_dont_share_a_definition(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(
        enterprise_data_fixture,
        settings,
        tmp_path,
        [READ_TOOLS],
        source_roles={"CRM": "VIEWER"},
    )
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    install_waiting(admin, workspace, template)
    first, second = install_waiting(admin, workspace, template)

    assert first.identity_definition_id != second.identity_definition_id
    # A template saved from both keeps them apart.
    (first_export, second_export), workspace_objects = export_for_template(
        [first, second]
    )
    assert first_export["run_as_identity_key"] != second_export["run_as_identity_key"]
    assert [identity["key"] for identity in workspace_objects["identities"]] == [
        first_export["run_as_identity_key"],
        second_export["run_as_identity_key"],
    ]


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_a_user_template_install_shares_the_identity_of_its_agents(
    enterprise_data_fixture, admin
):
    source = enterprise_data_fixture.create_workspace(user=admin)
    crm = enterprise_data_fixture.create_database_application(
        workspace=source, name="CRM"
    )
    identity = enterprise_data_fixture.create_identity(
        workspace=source, name="Author", role_uid="NO_ACCESS"
    )
    RoleAssignmentHandler().assign_role(
        identity, source, role=Role.objects.get(uid="VIEWER"), scope=crm.application_ptr
    )
    agents = [
        make_agent(enterprise_data_fixture, source, name, READ_TOOLS, identity)
        for name in ("First", "Second")
    ]
    copy = UserTemplateHandler().copy_applications(admin, [crm, *agents], name="Copy")
    revision = enterprise_data_fixture.create_user_template(user=admin, workspace=copy)
    content = UserTemplateHandler().serialize_template_content(revision)
    target = enterprise_data_fixture.create_workspace(user=admin)

    with transaction.atomic():
        action_type_registry.get_by_type(InstallTemplateActionType).do(
            admin, target, revision, content=content
        )

    first, second = AgentApplication.objects.filter(workspace=target).order_by("name")
    new_identity = run_identity(first)
    assert run_identity(second).id == new_identity.id
    assert roles_of(new_identity) == {
        (Database.objects.get(workspace=target).id, "VIEWER")
    }


@pytest.mark.django_db(transaction=True)
def test_the_exported_key_doesnt_hold_the_id_of_the_identity(
    enterprise_data_fixture, admin
):
    source = enterprise_data_fixture.create_workspace(user=admin)
    identity = enterprise_data_fixture.create_identity(
        workspace=source, role_uid="NO_ACCESS"
    )
    agents = [
        make_agent(enterprise_data_fixture, source, name, READ_TOOLS, identity)
        for name in ("First", "Second")
    ]

    (first, second), workspace_objects = export_for_template(agents)

    assert first["run_as_identity_key"] == second["run_as_identity_key"]
    assert first["run_as_identity_key"] != str(identity.id)
    assert "run_as_subject_id" not in first
    # Exported once, for both Agents.
    (exported,) = workspace_objects["identities"]
    assert exported["key"] == first["run_as_identity_key"]


@pytest.mark.django_db(transaction=True)
def test_a_template_install_keeps_what_refers_to_the_identity(
    enterprise_data_fixture, admin, settings, tmp_path
):
    source = enterprise_data_fixture.create_workspace()
    author = enterprise_data_fixture.create_identity(
        workspace=source, name="Author", role_uid="BUILDER"
    )
    database = database_referring_to(enterprise_data_fixture, source, author)
    agent = make_agent(enterprise_data_fixture, source, "Helper", READ_TOOLS, author)
    template = sync_applications(settings, tmp_path, [database, agent])
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    job = install(admin, workspace, template)

    assert job.state == JOB_FINISHED, job.human_readable_error
    identity = run_identity(AgentApplication.objects.get(workspace=workspace))
    assert identity.id != author.id
    assert references_of(Database.objects.get(workspace=workspace)) == referring_to(
        identity
    )


@pytest.mark.django_db(transaction=True)
def test_the_address_of_a_person_isnt_taken_for_an_identity(
    enterprise_data_fixture, admin, settings, tmp_path
):
    person = enterprise_data_fixture.create_user()
    source = enterprise_data_fixture.create_workspace(user=person)
    database = database_referring_to(enterprise_data_fixture, source, person)
    agent = make_agent(enterprise_data_fixture, source, "Helper", READ_TOOLS)
    template = sync_applications(settings, tmp_path, [database, agent])
    # A file that says the identity had the address of the person.
    edit_template(
        tmp_path,
        lambda content: content["workspace_objects"]["identities"][0].update(
            email=person.email
        ),
    )
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    job = install(admin, workspace, template)

    assert job.state == JOB_FINISHED, job.human_readable_error
    # The identity is created, but what the person made isn't given to it.
    run_identity(AgentApplication.objects.get(workspace=workspace))
    assert references_of(Database.objects.get(workspace=workspace)) == {
        "created_by": None,
        "last_modified_by": None,
        "collaborators": [],
        "view_owner": None,
        "filters": {""},
    }


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_a_file_import_recreates_the_identity(enterprise_data_fixture, admin):
    source = enterprise_data_fixture.create_workspace(user=admin)
    author = enterprise_data_fixture.create_identity(
        workspace=source, name="Author", role_uid="NO_ACCESS"
    )
    database = database_referring_to(enterprise_data_fixture, source, author)
    RoleAssignmentHandler().assign_role(
        author,
        source,
        role=Role.objects.get(uid="EDITOR"),
        scope=database.application_ptr,
    )
    agent = make_agent(enterprise_data_fixture, source, "Helper", WRITE_TOOLS, author)
    export_path = enterprise_data_fixture.export_workspace_applications_file(
        [database, agent]
    )
    target = enterprise_data_fixture.create_workspace(user=admin)

    import_zip(admin, target, export_path)

    assert manifest_of(export_path)["workspace_objects"] == {
        "identities": [
            {
                "key": ANY,
                "name": "Author",
                "email": author.email,
                "roles": [workspace_role("NO_ACCESS"), role_on(database, "EDITOR")],
            }
        ]
    }
    imported_agent = AgentApplication.objects.get(workspace=target)
    imported_database = Database.objects.get(workspace=target)
    identity = run_identity(imported_agent)
    assert identity.id != author.id
    assert identity.first_name == "Author"
    assert IdentityHandler.get_role_uid(identity) == "NO_ACCESS"
    assert roles_of(identity) == {(imported_database.id, "EDITOR")}
    assert AgentHandler().get_tool_configuration(imported_agent) == WRITE_CHOICES
    assert imported_agent.pending_tool_choices is None
    assert not IdentityDefinition.objects.filter(workspace=target).exists()
    assert references_of(imported_database) == referring_to(identity)


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_a_file_without_identities_has_no_workspace_objects(
    enterprise_data_fixture, admin
):
    source = enterprise_data_fixture.create_workspace(user=admin)
    database = enterprise_data_fixture.create_database_application(workspace=source)
    agent = enterprise_data_fixture.create_agent_application(workspace=source)

    export_path = enterprise_data_fixture.export_workspace_applications_file(
        [database, agent]
    )

    assert "workspace_objects" not in manifest_of(export_path)


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_an_identity_of_an_application_that_isnt_imported_isnt_created(
    enterprise_data_fixture, admin
):
    source = enterprise_data_fixture.create_workspace(user=admin)
    database = enterprise_data_fixture.create_database_application(
        workspace=source, name="CRM"
    )
    kept, left_out = [
        make_agent(
            enterprise_data_fixture,
            source,
            name,
            READ_TOOLS,
            enterprise_data_fixture.create_identity(
                workspace=source, name=name, role_uid="BUILDER"
            ),
        )
        for name in ("Kept", "Left out")
    ]
    export_path = enterprise_data_fixture.export_workspace_applications_file(
        [database, kept, left_out]
    )
    assert len(manifest_of(export_path)["workspace_objects"]["identities"]) == 2
    target = enterprise_data_fixture.create_workspace(user=admin)

    import_zip(admin, target, export_path, application_ids=[database.id, kept.id])

    imported_agent = AgentApplication.objects.get(workspace=target)
    identity = run_identity(imported_agent)
    assert [
        identity.first_name for identity in IdentityHandler().get_queryset(target)
    ] == ["Kept"]
    assert roles_of(identity) == {
        (Database.objects.get(workspace=target).id, "BUILDER")
    }
    assert not IdentityDefinition.objects.filter(workspace=target).exists()


@pytest.mark.django_db(transaction=True)
def test_a_definition_stays_while_a_waiting_agent_is_trashed(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(
        enterprise_data_fixture,
        settings,
        tmp_path,
        [READ_TOOLS, READ_TOOLS],
        source_roles={"CRM": "VIEWER"},
    )
    workspace = enterprise_data_fixture.create_workspace(user=admin)
    trashed, bound = install_waiting(admin, workspace, template)
    definition = IdentityDefinition.objects.get(workspace=workspace)
    identity = enterprise_data_fixture.create_identity(
        workspace=workspace, role_uid="BUILDER"
    )

    trash(admin, trashed)
    pick_identity(admin, bound, identity)

    # Kept for the restore of the trashed Agent.
    bound.refresh_from_db()
    assert bound.identity_definition_id is None
    assert IdentityDefinition.objects.filter(id=definition.id).exists()

    permanently_delete(trashed)

    assert not IdentityDefinition.objects.filter(id=definition.id).exists()


@pytest.mark.django_db(transaction=True)
def test_a_definition_is_deleted_with_its_last_waiting_agent(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(
        enterprise_data_fixture,
        settings,
        tmp_path,
        [READ_TOOLS, READ_TOOLS],
        source_roles={"CRM": "VIEWER"},
    )
    workspace = enterprise_data_fixture.create_workspace(user=admin)
    first, second = install_waiting(admin, workspace, template)
    definition = IdentityDefinition.objects.get(workspace=workspace)

    trash(admin, first)
    permanently_delete(first)

    # The other Agent still waits for it.
    assert IdentityDefinition.objects.filter(id=definition.id).exists()
    assert_waits(second)

    trash(admin, second)
    permanently_delete(second)

    assert not IdentityDefinition.objects.filter(id=definition.id).exists()


@pytest.mark.django_db(transaction=True)
def test_a_definition_is_deleted_when_an_identity_is_picked_by_hand(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(
        enterprise_data_fixture,
        settings,
        tmp_path,
        [READ_TOOLS, READ_TOOLS],
        source_roles={"CRM": "VIEWER"},
    )
    workspace = enterprise_data_fixture.create_workspace(user=admin)
    first, second = install_waiting(admin, workspace, template)
    definition = IdentityDefinition.objects.get(workspace=workspace)
    identity = enterprise_data_fixture.create_identity(
        workspace=workspace, role_uid="BUILDER"
    )

    pick_identity(admin, first, identity)

    # The other Agent still waits for it.
    first.refresh_from_db()
    assert first.identity_definition_id is None
    assert first.pending_tool_choices is None
    assert IdentityDefinition.objects.filter(id=definition.id).exists()
    assert_waits(second)

    pick_identity(admin, second, identity)

    assert not IdentityDefinition.objects.filter(id=definition.id).exists()
    assert run_identity(second).id == identity.id


@pytest.mark.django_db(transaction=True)
def test_an_application_of_another_type_can_refer_to_several_identities(
    enterprise_data_fixture, admin, settings, tmp_path
):
    database, site, agent = make_source(
        enterprise_data_fixture, [READ_TOOLS], with_site=True
    )
    author = run_identity(agent)
    editor = enterprise_data_fixture.create_identity(
        workspace=site.workspace, name="Editor", role_uid="EDITOR"
    )
    site_type = application_type_registry.get_by_model(site)
    export_site, import_site = site_type.export_serialized, site_type.import_serialized
    resolved = []

    def export_referring(application, config, *args, **kwargs):
        serialized = export_site(application, config, *args, **kwargs)
        serialized["acts_as"] = [
            config.identity_export.key_for(identity) for identity in (author, editor)
        ]
        return serialized

    def import_resolving(workspace, serialized, config, id_mapping, *args, **kwargs):
        resolved.extend(
            imported_identity(id_mapping, key) for key in serialized["acts_as"]
        )
        return import_site(workspace, serialized, config, id_mapping, *args, **kwargs)

    # A site that refers to the identity of the Agent and to one of its own, only
    # in this test.
    with patch.object(site_type, "export_serialized", export_referring):
        export, workspace_objects = export_for_template([database, site, agent])
    assert len(workspace_objects["identities"]) == 2
    write_template(tmp_path, "agent-kit", export, workspace_objects)
    settings.APPLICATION_TEMPLATES_DIR = str(tmp_path)
    CoreHandler().sync_templates(pattern="agent-kit")
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    with (
        patch.object(
            site_type,
            "get_imported_identity_keys",
            lambda serialized, config: set(serialized["acts_as"]),
        ),
        patch.object(site_type, "import_serialized", import_resolving),
    ):
        job = install(admin, workspace, Template.objects.get(slug="agent-kit"))

    assert job.state == JOB_FINISHED, job.human_readable_error
    identity = run_identity(AgentApplication.objects.get(workspace=workspace))
    # The site resolves both, and the first is the one the Agent acts as.
    assert [identity.first_name for identity in resolved] == ["Author", "Editor"]
    assert resolved[0].id == identity.id
    assert IdentityHandler().get_queryset(workspace).count() == 2
    # No role on the site, which refers to an identity like the Agent does.
    database_id = Database.objects.get(workspace=workspace).id
    assert roles_of(resolved[0]) == {(database_id, "BUILDER")}
    assert roles_of(resolved[1]) == {(database_id, "EDITOR")}


@pytest.mark.django_db(transaction=True)
def test_what_refers_to_an_address_two_identities_share_goes_to_the_first(
    enterprise_data_fixture, admin, settings, tmp_path
):
    source = enterprise_data_fixture.create_workspace()
    author = enterprise_data_fixture.create_identity(
        workspace=source, name="Author", role_uid="BUILDER"
    )
    database = database_referring_to(enterprise_data_fixture, source, author)
    first, second = [
        make_agent(
            enterprise_data_fixture,
            source,
            name,
            READ_TOOLS,
            identity,
        )
        for name, identity in (
            ("First", author),
            (
                "Second",
                enterprise_data_fixture.create_identity(
                    workspace=source, name="Other", role_uid="BUILDER"
                ),
            ),
        )
    ]
    template = sync_applications(settings, tmp_path, [database, first, second])

    def share_the_address(content):
        identities = content["workspace_objects"]["identities"]
        # The second identity says it had the address of the first.
        identities[1]["email"] = author.email
        # So does one that nothing refers to, which doesn't count.
        identities.insert(0, {**identities[0], "key": "unused", "name": "Unused"})

    edit_template(tmp_path, share_the_address)
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    job = install(admin, workspace, template)

    assert job.state == JOB_FINISHED, job.human_readable_error
    agents = AgentApplication.objects.filter(workspace=workspace).order_by("name")
    identity, other = [run_identity(agent) for agent in agents]
    assert identity.id != other.id
    assert references_of(Database.objects.get(workspace=workspace)) == referring_to(
        identity
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("importer_role", ["ADMIN", "BUILDER"])
def test_a_failed_file_import_leaves_no_identity_behind(
    enterprise_data_fixture, admin, importer_role
):
    source = enterprise_data_fixture.create_workspace(user=admin)
    author = enterprise_data_fixture.create_identity(
        workspace=source, name="Author", role_uid="NO_ACCESS"
    )
    database = enterprise_data_fixture.create_database_application(
        workspace=source, name="CRM"
    )
    agent = make_agent(enterprise_data_fixture, source, "Helper", WRITE_TOOLS, author)
    export_path = enterprise_data_fixture.export_workspace_applications_file(
        [database, agent]
    )
    # A builder may import, but not delete identities.
    importer = enterprise_data_fixture.create_user()
    target = enterprise_data_fixture.create_workspace(
        users=[admin], custom_permissions=[(importer, importer_role)]
    )

    deleted_receiver = MagicMock()
    identity_deleted.connect(deleted_receiver, weak=False)

    # A file import has no transaction that would roll the identity back.
    try:
        with (
            patch.object(
                AgentApplicationType,
                "import_serialized",
                side_effect=ValueError("boom"),
            ),
            patch.object(EnterpriseIdentityExtensionType, "before_delete") as before,
            pytest.raises(ValueError),
        ):
            import_zip(importer, target, export_path)
    finally:
        identity_deleted.disconnect(deleted_receiver)

    # Trashed, like the applications of a failed import.
    assert not IdentityHandler().get_queryset(target).exists()
    trashed = User.objects_and_identities.get(
        first_name="Author", workspaceuser__workspace=target
    )
    # The extensions clean up after it, as for any deleted identity.
    before.assert_called_once_with(trashed, importer)
    deleted_receiver.assert_called_once_with(
        signal=identity_deleted, sender=ANY, user=importer, identity=trashed
    )
    assert User.objects_and_identities.filter(
        profile__trashed=True, first_name="Author", workspaceuser__workspace=target
    ).exists()
    assert not IdentityDefinition.objects.filter(workspace=target).exists()
    assert list(
        AuditLogEntry.objects.filter(
            workspace_id=target.id, action_type__contains="identity"
        )
        .order_by("id")
        .values_list("action_type", flat=True)
    ) == ["create_scoped_identity", "delete_identity"]


@pytest.mark.django_db(transaction=True)
def test_identities_nothing_refers_to_arent_created(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(
        enterprise_data_fixture,
        settings,
        tmp_path,
        [WRITE_TOOLS],
        source_roles={"CRM": "EDITOR"},
    )

    def add_identities(content):
        identities = content["workspace_objects"]["identities"]
        identities.extend(
            {**identities[0], "key": f"extra-{index}", "name": f"Extra {index}"}
            for index in range(5)
        )

    edit_template(tmp_path, add_identities)
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    job = install(admin, workspace, template)

    assert job.state == JOB_FINISHED, job.human_readable_error
    agent = AgentApplication.objects.get(workspace=workspace)
    assert [identity.id for identity in IdentityHandler().get_queryset(workspace)] == [
        run_identity(agent).id
    ]
    # The others were never created, not created and deleted again.
    assert (
        AuditLogEntry.objects.filter(
            workspace_id=workspace.id, action_type="create_scoped_identity"
        ).count()
        == 1
    )


@pytest.mark.django_db(transaction=True)
def test_a_duplicate_of_a_waiting_agent_waits_for_the_same_identity(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(
        enterprise_data_fixture,
        settings,
        tmp_path,
        [READ_TOOLS],
        source_roles={"CRM": "VIEWER"},
    )
    workspace = enterprise_data_fixture.create_workspace(user=admin)
    (agent,) = install_waiting(admin, workspace, template)

    copy = CoreHandler().duplicate_application(admin, agent)

    assert copy.identity_definition_id == agent.identity_definition_id
    assert_waits(copy)


@pytest.mark.django_db(transaction=True)
def test_a_restored_snapshot_of_a_waiting_agent_waits_for_the_same_identity(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(
        enterprise_data_fixture,
        settings,
        tmp_path,
        [READ_TOOLS],
        source_roles={"CRM": "VIEWER"},
    )
    workspace = enterprise_data_fixture.create_workspace(user=admin)
    (agent,) = install_waiting(admin, workspace, template)
    snapshot = enterprise_data_fixture.create_snapshot(
        snapshot_from_application=agent, name=agent.name, created_by=admin
    )
    snapshots = SnapshotHandler()

    # A snapshot is taken into no workspace.
    snapshots.perform_create(snapshot, Progress(total=100))
    snapshot.refresh_from_db()
    restored = snapshots.perform_restore(
        snapshot, Progress(total=100), restored_by=admin
    )

    restored = AgentApplication.objects.get(id=restored.id)
    assert restored.identity_definition_id == agent.identity_definition_id
    assert_waits(restored)


@pytest.mark.django_db(transaction=True)
def test_a_waiting_agent_says_it_came_with_an_identity(
    enterprise_data_fixture, admin, settings, tmp_path
):
    template = sync_template(
        enterprise_data_fixture,
        settings,
        tmp_path,
        [READ_TOOLS, ([], [])],
        source_roles={"CRM": "VIEWER"},
    )
    workspace = enterprise_data_fixture.create_workspace(user=admin)
    install_waiting(admin, workspace, template)

    # Also the one without tools, whose triggers need the identity.
    assert {
        agent.name: AgentApplicationSerializer(agent).data["waits_for_identity"]
        for agent in AgentApplication.objects.filter(workspace=workspace)
    } == {"Agent 0": True, "Agent 1": True}


@pytest.mark.django_db(transaction=True)
def test_the_import_command_reads_the_identities_the_export_command_wrote(
    enterprise_data_fixture, admin, tmp_path, monkeypatch
):
    database, agent = make_source(
        enterprise_data_fixture, [READ_TOOLS], source_roles={"CRM": "VIEWER"}
    )
    target = enterprise_data_fixture.create_workspace(user=admin)
    monkeypatch.chdir(tmp_path)

    call_command("export_workspace_applications", agent.workspace_id, name="kit")
    call_command("import_workspace_applications", target.id, "kit")

    # Nobody imports, so the Agent waits for the identity the files describe.
    imported = AgentApplication.objects.get(workspace=target)
    assert_waits(imported)
    definition = IdentityDefinition.objects.get(workspace=target)
    assert imported.identity_definition_id == definition.id
    assert definition.name == "Author"
    assert definition.roles == [
        workspace_role("NO_ACCESS"),
        role_on(Database.objects.get(workspace=target), "VIEWER"),
    ]
