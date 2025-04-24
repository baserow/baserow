from unittest.mock import MagicMock

from django.db.transaction import Atomic

import pytest

from baserow.contrib.automation.workflows.job_types import (
    DuplicateAutomationWorkflowJobType,
)
from baserow.core.utils import ChildProgressBuilder


def test_atomic_context():
    context = DuplicateAutomationWorkflowJobType().transaction_atomic_context(None)
    assert isinstance(context, Atomic)


@pytest.mark.django_db
def test_prepare_values(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    values = {"workflow_id": workflow.id}

    result = DuplicateAutomationWorkflowJobType().prepare_values(values, user)

    assert result == {"original_automation_workflow": workflow}


@pytest.mark.django_db
def test_run(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    progress = ChildProgressBuilder.build(None, child_total=10)

    mock_job = MagicMock()
    mock_job.user = user
    mock_job.original_automation_workflow = workflow

    result = DuplicateAutomationWorkflowJobType().run(mock_job, progress)

    assert result.id != workflow.id
    assert mock_job.duplicated_automation_workflow == result
