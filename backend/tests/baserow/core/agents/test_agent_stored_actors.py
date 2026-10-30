from django.contrib.auth.models import AnonymousUser
from django.utils import translation
from django.utils.translation import gettext

import pytest

from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import DuplicateTableJob, Table
from baserow.core.cache import local_cache
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.handler import CoreHandler
from baserow.core.jobs.exceptions import JobDoesNotExist
from baserow.core.jobs.handler import JobHandler
from baserow.core.jobs.tasks import run_async_job
from baserow.core.registries import subject_type_registry
from baserow.core.user.utils import language_for_actor


@pytest.mark.django_db(transaction=True)
def test_agent_jobs_are_owned_by_the_stored_user_and_run_as_the_actor(data_fixture):
    table = data_fixture.create_database_table()
    TableHandler().create_created_by_and_last_modified_by_fields(table)
    agent = data_fixture.create_agent(workspace=table.database.workspace)
    RowHandler().create_row(agent, table)

    job = JobHandler().create_and_start_job(
        agent, "duplicate_table", table_id=table.id, sync=True
    )

    assert job.finished
    assert job.user == agent.user
    assert job.actor == agent
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
    assert row.created_by_id == agent.user_id
    assert row.last_modified_by_id == agent.user_id

    other_agent = data_fixture.create_agent(workspace=agent.workspace)
    with pytest.raises(JobDoesNotExist):
        JobHandler.get_job(other_agent, job.id)
    assert not JobHandler.get_jobs_for_user(other_agent, None, [job.id]).exists()


@pytest.mark.django_db(transaction=True)
def test_a_queued_job_cannot_act_for_a_trashed_agent(data_fixture):
    table = data_fixture.create_database_table()
    agent = data_fixture.create_agent(workspace=table.database.workspace)
    job = DuplicateTableJob.objects.create(user=agent.user, original_table=table)
    agent.trashed = True
    agent.save(update_fields=["trashed"])

    with local_cache.context(), pytest.raises(UserNotInWorkspace):
        run_async_job(job.id)

    job.refresh_from_db()
    assert job.failed
    assert job.duplicated_table_id is None
    assert Table.objects.count() == 1
    assert subject_type_registry.actor_for_user(agent.user).trashed


@pytest.mark.django_db
def test_jobs_require_an_actor_with_a_stored_user(data_fixture):
    data_fixture.register_temp_job_types()
    legacy_agent = data_fixture.create_agent()
    legacy_agent.user = None
    legacy_agent.save(update_fields=["user"])

    for actor in (legacy_agent, AnonymousUser(), None):
        with pytest.raises(ValueError, match="stored user"):
            JobHandler().create_and_start_job(actor, "tmp_job_type_1")
        assert not JobHandler.get_jobs_for_user(actor, None, None).exists()
        with pytest.raises(JobDoesNotExist):
            JobHandler.get_job(actor, 1)


@pytest.mark.django_db
@pytest.mark.parametrize("language,field_name", [("en", "Name"), ("fr", "Nom")])
def test_agents_create_tables_and_initialize_applications_in_their_language(
    data_fixture, language, field_name
):
    agent = data_fixture.create_agent()
    profile = agent.user.profile
    profile.language = language
    profile.save(update_fields=["language"])
    assert language_for_actor(agent) == language

    database = CoreHandler().create_application(
        agent, agent.workspace, "database", name="Data", init_with_data=True
    )
    assert database.table_set.get().field_set.get(primary=True).name == field_name
    table, _ = TableHandler().create_table(
        agent, database, "Another", fill_example=False
    )
    assert table.field_set.get(primary=True).name == field_name


def test_actors_without_a_user_have_no_language():
    assert language_for_actor(None) is None
    assert language_for_actor(AnonymousUser()) is None


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
    profile = agent.user.profile
    profile.language = language
    profile.save(update_fields=["language"])
    handler = CoreHandler()

    builder = handler.create_application(
        agent, agent.workspace, "builder", name="Site", init_with_data=True
    )
    homepage_name = "Homepage" if language == "en" else "Page d'accueil"
    homepage = builder.page_set.get(name=homepage_name)
    assert homepage.element_set.exists()
    builder_integration = builder.integrations.get().specific
    assert builder_integration.authorized_subject_type == "core.Agent"
    assert builder_integration.authorized_subject_id == agent.id
    builder_source = DataSourceService().create_data_source(
        agent, homepage, service_type=None
    )
    assert builder_source.name == (
        "Data source" if language == "en" else "Source de données"
    )

    automation = handler.create_application(
        agent, agent.workspace, "automation", name="Flows", init_with_data=True
    )
    with translation.override(language):
        assert automation.workflows.get().name == gettext("Workflow")
    assert not automation.workflows.get().notification_recipients.exists()
    automation_integration = automation.integrations.get().specific
    assert automation_integration.authorized_subject_type == "core.Agent"
    assert automation_integration.authorized_subject_id == agent.id

    dashboard = handler.create_application(
        agent, agent.workspace, "dashboard", name="Metrics", init_with_data=True
    )
    dashboard_integration = dashboard.integrations.get().specific
    assert dashboard_integration.authorized_subject_type == "core.Agent"
    assert dashboard_integration.authorized_subject_id == agent.id
    dashboard_source = DashboardDataSourceService().create_data_source(
        agent, dashboard.id, service_type_registry.get("local_baserow_aggregate_rows")
    )
    assert dashboard_source.name == (
        "Data source" if language == "en" else "Source de données"
    )
