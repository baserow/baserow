from django.db import transaction

import pytest

from baserow.contrib.builder.pages.job_types import DuplicatePageJobType
from baserow.contrib.builder.pages.models import Page
from baserow.core.action.handler import ActionHandler
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow.core.jobs.constants import JOB_FINISHED
from baserow.core.jobs.handler import JobHandler
from baserow.test_utils.helpers import assert_undo_redo_actions_are_valid


@pytest.mark.django_db(transaction=True)
def test_can_submit_duplicate_page_job(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)

    page_count = Page.objects.filter(builder=builder).count()

    duplicate_page_job = JobHandler().create_and_start_job(
        user,
        DuplicatePageJobType.type,
        page_id=page.id,
    )

    assert Page.objects.filter(builder=builder).count() == page_count + 1

    duplicate_page_job.refresh_from_db()
    assert duplicate_page_job.state == JOB_FINISHED
    assert duplicate_page_job.original_page_id == page.id
    assert duplicate_page_job.duplicated_page_id is not None


@pytest.mark.django_db(transaction=True)
@pytest.mark.undo_redo
def test_can_undo_redo_duplicate_page_job(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)

    duplicate_page_job = JobHandler().create_and_start_job(
        user,
        DuplicatePageJobType.type,
        page_id=page.id,
        user_session_id=session_id,
    )
    duplicate_page_job.refresh_from_db()
    duplicated_page_id = duplicate_page_job.duplicated_page_id
    assert Page.objects.filter(id=duplicated_page_id).exists()

    scope = [ApplicationActionScopeType.value(application_id=builder.id)]

    with transaction.atomic():
        actions_undone = ActionHandler.undo(user, scope, session_id)
        assert_undo_redo_actions_are_valid(actions_undone, [DuplicatePageJobType])

    # The duplicated page is trashed by the undo; the original remains.
    assert not Page.objects.filter(id=duplicated_page_id).exists()
    assert Page.objects.filter(id=page.id).exists()

    with transaction.atomic():
        actions_redone = ActionHandler.redo(user, scope, session_id)
        assert_undo_redo_actions_are_valid(actions_redone, [DuplicatePageJobType])

    assert Page.objects.filter(id=duplicated_page_id).exists()
