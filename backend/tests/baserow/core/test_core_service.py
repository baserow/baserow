from django.db import connection
from django.test.utils import CaptureQueriesContext

import pytest

from baserow.core.service import CoreService


@pytest.mark.django_db
def test_list_applications_in_workspace(data_fixture, bypass_check_permissions):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    application_in_another_workspace = data_fixture.create_database_application()

    with CaptureQueriesContext(connection) as captured:
        applications = list(
            CoreService().list_applications_in_workspace(
                user, workspace, specific=False
            )
        )

    assert len(captured) == 1

    assert len(applications) == 1
    assert applications[0].id == application.id
