import json

import pytest

from baserow.contrib.automation.application_types import AutomationApplicationType
from baserow.core.registries import ImportExportConfig


@pytest.mark.django_db
def test_automation_export_serialized(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(
        name="Automation 1", user=user
    )
    serialized = AutomationApplicationType().export_serialized(
        automation, ImportExportConfig(include_permission_data=True)
    )
    serialized = json.loads(json.dumps(serialized))

    assert serialized == {
        "id": automation.id,
        "name": automation.name,
        "order": automation.order,
        "type": "automation",
    }


@pytest.mark.django_db
def test_automation_import_serialized(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    id_mapping = {}
    serialized = {
        "id": "999",
        "name": "Automation 1",
        "order": 99,
        "type": "automation",
    }

    automation = AutomationApplicationType().import_serialized(
        workspace,
        serialized,
        ImportExportConfig(include_permission_data=True),
        id_mapping,
    )

    assert automation.name == "Automation 1"
    assert automation.order == 99
