import pytest

from baserow.contrib.automation.handler import AutomationHandler
from baserow.core.exceptions import ApplicationDoesNotExist


@pytest.mark.django_db
def test_get_automation(data_fixture):
    automation = data_fixture.create_automation_application()
    assert AutomationHandler().get_automation(automation.id).id == automation.id


@pytest.mark.django_db
def test_get_automation_does_not_exist(data_fixture):
    with pytest.raises(ApplicationDoesNotExist):
        AutomationHandler().get_automation(9999)
