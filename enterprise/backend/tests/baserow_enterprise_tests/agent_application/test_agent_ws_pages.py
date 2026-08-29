import pytest

from baserow.core.handler import CoreHandler
from baserow_enterprise.agent_application.ws.pages import AgentApplicationPageType


@pytest.mark.django_db
def test_agent_application_page_type_can_add(data_fixture):
    user = data_fixture.create_user()
    outsider = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = CoreHandler().create_application(
        user, workspace, "agent", init_with_data=True, name="Agent"
    )

    page_type = AgentApplicationPageType()

    assert page_type.can_add(user, None, application.id) is True
    assert page_type.can_add(outsider, None, application.id) is False
    assert page_type.can_add(user, None, 0) is False
    assert (
        page_type.get_group_name(application.id)
        == f"agent_application-{application.id}"
    )
