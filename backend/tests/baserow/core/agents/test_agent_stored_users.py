from django.utils import translation
from django.utils.translation import gettext

import pytest

from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import DuplicateTableJob, Table
from baserow.core.agents.handler import AgentHandler
from baserow.core.cache import local_cache
from baserow.core.exceptions import PermissionException
from baserow.core.handler import CoreHandler
from baserow.core.jobs.exceptions import JobDoesNotExist
from baserow.core.jobs.handler import JobHandler
from baserow.core.jobs.tasks import run_async_job
from baserow.core.models import WorkspaceUser


@pytest.mark.django_db(transaction=True)
def test_agent_jobs_keep_user_ownership_and_row_credits(data_fixture):
    table = data_fixture.create_database_table()
    TableHandler().create_created_by_and_last_modified_by_fields(table)
    agent = data_fixture.create_agent(workspace=table.database.workspace)
    RowHandler().create_row(agent, table)

    job = JobHandler().create_and_start_job(
        agent, "duplicate_table", table_id=table.id, sync=True
    )

    assert job.finished
    assert job.user == agent
    assert JobHandler.get_job(agent, job.id).id == job.id
    assert list(
        JobHandler.get_jobs_for_user(agent, None, None).values_list("id", flat=True)
    ) == [job.id]
    assert list(
        JobHandler.get_jobs_for_user(
            agent, None, [job.id], base_model=DuplicateTableJob
        )
    ) == [job]
    row = job.duplicated_table.get_model().objects.get()
    assert row.created_by_id == agent.id
    assert row.last_modified_by_id == agent.id

    other_agent = data_fixture.create_agent(workspace=AgentHandler.get_workspace(agent))
    with pytest.raises(JobDoesNotExist):
        JobHandler.get_job(other_agent, job.id)
    assert not JobHandler.get_jobs_for_user(other_agent, None, [job.id]).exists()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("revocation", ["trash", "disable", "membership", "role"])
def test_queued_agent_job_rechecks_current_authority(data_fixture, revocation):
    table = data_fixture.create_database_table()
    agent = data_fixture.create_agent(workspace=table.database.workspace)
    job = DuplicateTableJob.objects.create(user=agent, original_table=table)
    if revocation == "trash":
        agent.profile.trashed = True
        agent.profile.save(update_fields=["trashed"])
    elif revocation == "disable":
        agent.is_active = False
        agent.save(update_fields=["is_active"])
    elif revocation == "membership":
        WorkspaceUser.objects_and_trash.filter(user=agent).delete()
    else:
        WorkspaceUser.objects_and_trash.filter(user=agent).update(
            permissions="NO_ACCESS"
        )

    with local_cache.context(), pytest.raises(PermissionException):
        run_async_job(job.id)

    job.refresh_from_db()
    assert job.failed
    assert job.duplicated_table_id is None
    assert Table.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("language,field_name", [("en", "Name"), ("fr", "Nom")])
def test_agents_create_tables_and_initialize_applications_in_their_language(
    data_fixture, language, field_name
):
    agent = data_fixture.create_agent()
    profile = agent.profile
    profile.language = language
    profile.save(update_fields=["language"])

    database = CoreHandler().create_application(
        agent,
        AgentHandler.get_workspace(agent),
        "database",
        name="Data",
        init_with_data=True,
    )
    assert database.table_set.get().field_set.get(primary=True).name == field_name
    table, _ = TableHandler().create_table(
        agent, database, "Another", fill_example=False
    )
    assert table.field_set.get(primary=True).name == field_name


@pytest.mark.django_db
@pytest.mark.parametrize("language", ["en", "fr"])
def test_agent_builder_automation_and_dashboard_initialization_uses_the_actor(
    data_fixture, language
):
    from baserow.contrib.builder.data_sources.service import DataSourceService
    from baserow.contrib.dashboard.data_sources.service import (
        DashboardDataSourceService,
    )
    from baserow.core.services.registries import service_type_registry

    agent = data_fixture.create_agent()
    profile = agent.profile
    profile.language = language
    profile.save(update_fields=["language"])
    handler = CoreHandler()

    builder = handler.create_application(
        agent,
        AgentHandler.get_workspace(agent),
        "builder",
        name="Site",
        init_with_data=True,
    )
    homepage_name = "Homepage" if language == "en" else "Page d'accueil"
    homepage = builder.page_set.get(name=homepage_name)
    assert homepage.element_set.exists()
    builder_integration = builder.integrations.get().specific
    assert builder_integration.authorized_subject_type == "auth.User"
    assert builder_integration.authorized_subject_id == agent.id
    builder_source = DataSourceService().create_data_source(
        agent, homepage, service_type=None
    )
    assert builder_source.name == (
        "Data source" if language == "en" else "Source de données"
    )

    automation = handler.create_application(
        agent,
        AgentHandler.get_workspace(agent),
        "automation",
        name="Flows",
        init_with_data=True,
    )
    with translation.override(language):
        assert automation.workflows.get().name == gettext("Workflow")
    assert not automation.workflows.get().notification_recipients.exists()
    automation_integration = automation.integrations.get().specific
    assert automation_integration.authorized_subject_type == "auth.User"
    assert automation_integration.authorized_subject_id == agent.id

    dashboard = handler.create_application(
        agent,
        AgentHandler.get_workspace(agent),
        "dashboard",
        name="Metrics",
        init_with_data=True,
    )
    dashboard_integration = dashboard.integrations.get().specific
    assert dashboard_integration.authorized_subject_type == "auth.User"
    assert dashboard_integration.authorized_subject_id == agent.id
    dashboard_source = DashboardDataSourceService().create_data_source(
        agent, dashboard.id, service_type_registry.get("local_baserow_aggregate_rows")
    )
    assert dashboard_source.name == (
        "Data source" if language == "en" else "Source de données"
    )


@pytest.mark.django_db
def test_agent_snapshot_keeps_credits_and_rechecks_restore_authority(data_fixture):
    from baserow.core.models import Snapshot
    from baserow.core.snapshots.handler import SnapshotHandler
    from baserow.core.utils import Progress

    table = data_fixture.create_database_table()
    agent = data_fixture.create_agent(workspace=table.database.workspace)
    RowHandler().create_row(agent, table)
    snapshot = data_fixture.create_snapshot(
        snapshot_from_application=table.database,
        created_by=agent,
        name="Agent snapshot",
    )
    handler = SnapshotHandler()
    snapshot = Snapshot.objects.select_related("created_by").get(id=snapshot.id)

    handler.perform_create(snapshot, Progress(total=100))

    snapshot.refresh_from_db()
    copied = Table.objects.get(database=snapshot.snapshot_to_application)
    row = copied.get_model().objects.get()
    assert row.created_by_id == agent.id
    assert row.last_modified_by_id == agent.id
    assert snapshot.created_by == agent

    agent.is_active = False
    agent.save(update_fields=["is_active"])
    snapshot = Snapshot.objects.select_related("created_by").get(id=snapshot.id)
    with local_cache.context(), pytest.raises(PermissionException):
        handler.perform_restore(snapshot, Progress(total=100))


@pytest.mark.django_db
@pytest.mark.parametrize("state", ["disabled", "trashed"])
def test_snapshot_retains_unavailable_agent_credits_and_shared_view_owner(
    data_fixture, state
):
    from baserow.core.models import Snapshot
    from baserow.core.snapshots.handler import SnapshotHandler
    from baserow.core.utils import Progress

    human = data_fixture.create_user()
    table = data_fixture.create_database_table(user=human)
    agent = data_fixture.create_agent(workspace=table.database.workspace)
    RowHandler().create_row(agent, table)
    shared_view = data_fixture.create_grid_view(table=table, owned_by=agent)
    data_fixture.create_grid_view(
        table=table,
        owned_by=agent,
        ownership_type="personal",
        name="Invalid machine private view",
    )
    if state == "disabled":
        agent.is_active = False
        agent.save(update_fields=["is_active"])
    else:
        agent.profile.trashed = True
        agent.profile.save(update_fields=["trashed"])
    snapshot = data_fixture.create_snapshot(
        snapshot_from_application=table.database,
        created_by=human,
        name="Retained credits",
    )

    SnapshotHandler().perform_create(snapshot, Progress(total=100))

    snapshot = Snapshot.objects.get(id=snapshot.id)
    copied = Table.objects.get(database=snapshot.snapshot_to_application)
    row = copied.get_model().objects.get()
    assert row.created_by_id == agent.id
    assert row.last_modified_by_id == agent.id
    assert copied.view_set.get(name=shared_view.name).owned_by_id == agent.id
    assert not copied.view_set.filter(
        ownership_type="personal", owned_by=agent
    ).exists()
