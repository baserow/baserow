import threading
from contextlib import nullcontext
from unittest.mock import patch

from django.db import connection, transaction

import pytest

from baserow.core.jobs.constants import JOB_FAILED
from baserow.core.jobs.handler import JobHandler
from baserow.core.models import Template, TemplateCategory
from baserow.core.user_templates.job_types import CreateUserTemplateJobType
from tests.baserow.core.user_templates.utils import (
    ICON,
    create_template,
    fail_on_import,
    install_marks,
    queued,
    request_download,
    request_install,
    run_job,
    turn_user_templates,
)

TURNED_OFF = "User templates have been turned off by the instance administrator."


def turn_off_elsewhere(data_fixture):
    """Turns user templates off in another connection, like an admin meanwhile."""

    def turn_off():
        try:
            turn_user_templates(data_fixture, False)
        finally:
            connection.close()

    thread = threading.Thread(target=turn_off)
    thread.start()
    thread.join()


def request_create(user, workspace, database):
    with queued(), transaction.atomic():
        return JobHandler().create_and_start_job(
            user,
            CreateUserTemplateJobType.type,
            workspace_id=workspace.id,
            application_ids=[database.id],
            name="New",
            description="",
            icon=ICON,
            category_ids=[TemplateCategory.objects.create(name="Cat").id],
        )


def before_saving_the_template(data_fixture):
    save_template = CreateUserTemplateJobType._save_template

    def turn_off_then_save(self, job, revision):
        turn_off_elsewhere(data_fixture)
        return save_template(self, job, revision)

    return patch.object(CreateUserTemplateJobType, "_save_template", turn_off_then_save)


@install_marks
@pytest.mark.parametrize(
    "job_type,window",
    [
        ("create", "start"),
        ("create", "before commit"),
        ("install", "start"),
        ("install", "before commit"),
        ("download", "start"),
    ],
)
def test_running_jobs_fail_when_turned_off(data_fixture, job_type, window):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    template = create_template(
        data_fixture, user, "public" if job_type == "download" else "private"
    )
    templates_before = set(Template.objects.values_list("id", flat=True))
    job = {
        "create": lambda: request_create(user, workspace, database),
        "install": lambda: request_install(user, workspace, template),
        "download": lambda: request_download(data_fixture.create_user(), template),
    }[job_type]()
    if window == "start":
        turn_off_elsewhere(data_fixture)
    during = {
        ("create", "before commit"): before_saving_the_template(data_fixture),
        ("install", "before commit"): fail_on_import(
            None, on_call=1, before=lambda: turn_off_elsewhere(data_fixture)
        ),
    }.get((job_type, window), nullcontext())

    with during:
        job = run_job(job)

    assert job.state == JOB_FAILED
    assert job.error_code == "UserTemplatesDisabled"
    assert job.human_readable_error == TURNED_OFF
    assert set(Template.objects.values_list("id", flat=True)) == templates_before
    assert list(workspace.application_set.values_list("id", flat=True)) == [database.id]
