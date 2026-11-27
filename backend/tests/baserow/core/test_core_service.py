from django.db import connection
from django.test.utils import CaptureQueriesContext

import pytest

from baserow.core.service import CoreService


@pytest.mark.django_db
def test_list_applications_in_workspace(data_fixture, bypass_check_permissions):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    shared_application = data_fixture.create_shared_application(workspace=workspace)
    application = data_fixture.create_database_application(workspace=workspace, order=1)
    application_in_another_workspace = data_fixture.create_database_application()

    with CaptureQueriesContext(connection) as captured:
        applications = list(
            CoreService().list_applications_in_workspace(
                user, workspace, specific=False
            )
        )

    # One query looks for listed workspaces without a shared application.
    # TODO ZDM: 1 once the lazy creation is removed,
    # https://github.com/baserow/baserow/issues/6758
    assert len(captured) == 2

    assert [a.id for a in applications] == [shared_application.id, application.id]
