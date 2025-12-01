import pytest

from baserow.contrib.automation.models import Automation
from baserow.core.handler import CoreHandler


@pytest.mark.django_db
def test_can_duplicate_automation_application(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)

    automation_clone = CoreHandler().duplicate_application(user, automation)

    assert automation_clone.id != automation.id
    assert automation_clone.name.startswith(automation.name)

    assert Automation.objects.count() == 2
