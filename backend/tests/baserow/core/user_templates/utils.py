from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.db import connection
from django.utils import timezone

import pytest

from baserow.contrib.automation.nodes.node_types import (
    LocalBaserowFieldsUpdatedTriggerNodeType,
)
from baserow.contrib.builder.elements.models import ChoiceElement
from baserow.contrib.database.application_types import DatabaseApplicationType
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.integrations.local_baserow.models import LocalBaserowAggregateRows
from baserow.core.cache import local_cache
from baserow.core.exceptions import PermissionDenied
from baserow.core.handler import CoreHandler
from baserow.core.job_types import InstallTemplateJobType
from baserow.core.jobs.exceptions import JobNotCancellable
from baserow.core.jobs.handler import JobHandler
from baserow.core.jobs.tasks import run_async_job
from baserow.core.models import Template, TemplateCategory
from baserow.core.operations import ExportWorkspaceOperationType
from baserow.core.storage import get_default_storage
from baserow.core.user_templates.constants import USER_TEMPLATE_DELETION_GRACE_PERIOD
from baserow.core.user_templates.handler import UserTemplateHandler
from baserow.core.user_templates.job_types import CreateUserTemplateJobType
from baserow.core.user_templates.models import CreateUserTemplateJob
from baserow.core.user_templates.service import UserTemplateService
from baserow.core.user_templates.tasks import delete_orphaned_user_template_workspaces

ICON = "iconoir-view-grid"
OTHER_ICON = "iconoir-calendar"

# The install serializes in its own transactions, so it runs outside a test
# transaction.
install_test = [
    pytest.mark.import_export_workspace,
    pytest.mark.django_db(transaction=True),
    pytest.mark.usefixtures("use_tmp_media_root"),
]

CLEARED_KEYS = {
    "table_id",
    "field_id",
    "view_id",
    "authorized_subject_type",
    "authorized_subject_id",
    "password",
}


def serialized_content(revision):
    """The content of the revision as an install reads it."""

    return UserTemplateHandler().serialize_template_content(revision)


def find_values(data, keys):
    if isinstance(data, dict):
        for key, value in data.items():
            if key in keys:
                yield key, value
            yield from find_values(value, keys)
    elif isinstance(data, list):
        for item in data:
            yield from find_values(item, keys)


def start_job(user, workspace, applications, **kwargs):
    kwargs.setdefault("name", "My template")
    kwargs.setdefault("description", "What it does")
    kwargs.setdefault("icon", ICON)
    if "category_ids" not in kwargs:
        kwargs["category_ids"] = [TemplateCategory.objects.create(name="Cat").id]
    return JobHandler().create_and_start_job(
        user,
        CreateUserTemplateJobType.type,
        sync=True,
        workspace_id=workspace.id,
        application_ids=[application.id for application in applications],
        **kwargs,
    )


def update_details(user, template, **kwargs):
    kwargs.setdefault("name", "Renamed")
    kwargs.setdefault("description", "What it does now")
    kwargs.setdefault("icon", OTHER_ICON)
    if "category_ids" not in kwargs:
        kwargs["category_ids"] = [TemplateCategory.objects.create(name="New").id]
    return JobHandler().create_and_start_job(
        user,
        CreateUserTemplateJobType.type,
        sync=True,
        template_id=template.id,
        **kwargs,
    )


def update_content(user, template, workspace, applications, **kwargs):
    return JobHandler().create_and_start_job(
        user,
        CreateUserTemplateJobType.type,
        sync=True,
        template_id=template.id,
        workspace_id=workspace.id,
        application_ids=[application.id for application in applications],
        **kwargs,
    )


def queued():
    """Starts jobs without running them, like jobs waiting for a worker."""

    return patch("baserow.core.jobs.handler.run_async_job")


def run_job(job):
    """Runs the task of the job like a worker, and returns the job as it ended."""

    # A worker clears the local cache before each task, see `config/celery.py`.
    local_cache.clear()
    run_async_job(job.id)
    return type(job).objects.get(id=job.id)


def install_marks(test):
    for mark in reversed(install_test):
        test = mark(test)
    return test


def request_install(user, workspace, template, latest=False):
    """Requests an install without running it, like a job waiting in the queue."""

    with queued():
        return JobHandler().create_and_start_job(
            user,
            InstallTemplateJobType.type,
            workspace_id=workspace.id,
            template_id=template.id,
            latest=latest,
        )


def install(user, workspace, template, latest=False):
    return run_job(request_install(user, workspace, template, latest))


def create_template(data_fixture, user, **kwargs):
    """A user template whose content can be copied, without running a job."""

    workspace = data_fixture.create_workspace(name="Content")
    data_fixture.create_database_application(workspace=workspace)
    kwargs.setdefault("icon", ICON)
    return data_fixture.create_user_template(user=user, workspace=workspace, **kwargs)


def store_archive(name="template.zip"):
    return get_default_storage().save(
        f"template-revisions/{name}", ContentFile(b"archive")
    )


def create_content(data_fixture, name="Content", archive="template.zip"):
    """A workspace with a database and an archive, like the content of a revision."""

    workspace = data_fixture.create_workspace(name=name)
    data_fixture.create_database_application(workspace=workspace)
    return workspace, store_archive(archive)


def long_ago():
    """Before the grace period of a template deleted now."""

    return timezone.now() - USER_TEMPLATE_DELETION_GRACE_PERIOD - timedelta(hours=1)


def purge():
    UserTemplateHandler().delete_marked_templates()


def purge_after_the_grace_period():
    """Lets the grace period of the deleted templates pass, then runs the cleanup."""

    Template.objects.filter(marked_for_deletion_at__isnull=False).update(
        marked_for_deletion_at=long_ago()
    )
    delete_orphaned_user_template_workspaces()


def deny_export():
    """Refuses the export of a workspace, like a role that can't export."""

    check_permissions = CoreHandler.check_permissions

    def check_permissions_without_export(self, actor, operation_name, *args, **kw):
        if operation_name == ExportWorkspaceOperationType.type:
            raise PermissionDenied()
        return check_permissions(self, actor, operation_name, *args, **kw)

    return patch.object(
        CoreHandler, "check_permissions", check_permissions_without_export
    )


def fail_on_import(exception, on_call=2, before=None):
    """
    Patches the import of a database so that the import of the `on_call`-th
    database raises `exception`, if given, after calling `before`, if given.
    """

    import_serialized = DatabaseApplicationType.import_serialized
    calls = []

    def import_serialized_raising(self, *args, **kwargs):
        calls.append(args)
        if len(calls) == on_call:
            if before is not None:
                before()
            if exception is not None:
                raise exception
        return import_serialized(self, *args, **kwargs)

    return patch.object(
        DatabaseApplicationType, "import_serialized", import_serialized_raising
    )


def cancel_in_another_connection(outcome, job_model, **lookup):
    """
    Cancels the job, like a request in its own connection, from a test thread, and
    records in `outcome["cancel"]` whether the cancel was accepted or refused.
    """

    try:
        JobHandler.cancel_job(job_model.objects.get(**lookup))
        outcome["cancel"] = "accepted"
    except JobNotCancellable:
        outcome["cancel"] = "refused"
    finally:
        connection.close()


def create_database_source(data_fixture):
    """A workspace of a user with only a database, for tests of the job flow."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    return {"user": user, "workspace": workspace, "database": database}


def create_source(data_fixture):
    """
    A workspace of two members with a database, a builder and an automation, each
    holding something the copy must not carry over.
    """

    user = data_fixture.create_user(email="owner@example.com")
    member = data_fixture.create_user(email="member@example.com")
    workspace = data_fixture.create_workspace(user=user, members=[member])

    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    text_field = data_fixture.create_text_field(table=table, primary=True)
    collaborators_field = data_fixture.create_multiple_collaborators_field(table=table)
    RowHandler().create_row(
        user,
        table,
        values={
            text_field.db_column: "Row",
            collaborators_field.db_column: [{"id": user.id}, {"id": member.id}],
        },
    )
    view = data_fixture.create_grid_view(table=table, name="Shared")
    for owner in [user, member]:
        data_fixture.create_grid_view(
            table=table,
            name=f"Personal of {owner.email}",
            ownership_type="personal",
            owned_by=owner,
        )

    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user
    )
    list_rows = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page, integration=integration, table=table, view=view, name="List"
    )
    data_fixture.create_local_baserow_table_service_sort(
        service=list_rows.service, field=text_field, order_by="ASC", order=0
    )
    data_fixture.create_local_baserow_table_service_filter(
        service=list_rows.service, field=text_field, value="Row"
    )
    data_fixture.create_builder_choice_element(
        page=page,
        option_type=ChoiceElement.OPTION_TYPE.FORMULAS,
        formula_value=(
            f"get('data_source_context.{list_rows.id}.{text_field.db_column}.*.value')"
        ),
    )
    data_fixture.create_builder_data_source(
        page=page,
        service_model_class=LocalBaserowAggregateRows,
        integration=integration,
        table=table,
        field=text_field,
        aggregation_type="empty_count",
        name="Aggregate",
    )

    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
        dashboard=dashboard,
        integration_args={"authorized_user": user},
        table=table,
        field=text_field,
        aggregation_type="empty_count",
    )

    automation = data_fixture.create_automation_application(workspace=workspace)
    workflow = data_fixture.create_automation_workflow(
        automation=automation, create_trigger=False
    )
    data_fixture.create_core_http_trigger_node(workflow=workflow)
    data_fixture.create_automation_node(
        workflow=data_fixture.create_automation_workflow(
            automation=automation, create_trigger=False
        ),
        type=LocalBaserowFieldsUpdatedTriggerNodeType.type,
        service=data_fixture.create_local_baserow_fields_updated_service(
            integration=data_fixture.create_local_baserow_integration(
                application=automation, user=user
            ),
            table=table,
            fields=[text_field],
        ),
    )
    data_fixture.create_smtp_integration(
        application=automation, username="smtp-user", password="smtp-secret"
    )

    return {
        "user": user,
        "workspace": workspace,
        "database": database,
        "table": table,
        "text_field": text_field,
        "builder": builder,
        "dashboard": dashboard,
        "automation": automation,
    }


def copied_applications(template):
    return {
        application.get_type().type: application.specific
        for application in template.workspace.application_set.all()
    }


@contextmanager
def another_run_after_the_copy(error=None):
    """
    Runs the latest job again, like a redelivery of its task, right after the
    first run copied its content, and then raises `error` in the first run if
    given. Yields the list the other run is added to.
    """

    copy_applications = UserTemplateService.copy_applications
    calls, other_runs = [], []

    def copy_then_run_again(service, *args, **kwargs):
        content = copy_applications(service, *args, **kwargs)
        calls.append(content)
        if len(calls) == 1:
            other_runs.append(run_job(CreateUserTemplateJob.objects.latest("id")))
            if error is not None:
                raise error
        return content

    with patch.object(UserTemplateService, "copy_applications", copy_then_run_again):
        yield other_runs
