import json

import pytest

from baserow.contrib.whiteboard.application_types import WhiteboardApplicationType
from baserow.contrib.whiteboard.models import Whiteboard
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig


@pytest.mark.django_db
def test_create_whiteboard_application_via_core_handler(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = CoreHandler().create_application(
        user,
        workspace,
        type_name="whiteboard",
        name="Board 1",
    )
    assert isinstance(application, Whiteboard)
    assert application.name == "Board 1"
    assert application.workspace_id == workspace.id
    assert application.content == {}


@pytest.mark.django_db
def test_whiteboard_export_serialized(data_fixture):
    user = data_fixture.create_user()
    whiteboard = data_fixture.create_whiteboard_application(name="Board 1", user=user)
    whiteboard.content = {
        "elements": [{"id": "abc"}],
        "appState": {"viewBackgroundColor": "#fff"},
    }
    whiteboard.save()

    serialized = WhiteboardApplicationType().export_serialized(
        whiteboard, ImportExportConfig(include_permission_data=True)
    )
    serialized = json.loads(json.dumps(serialized))

    assert serialized == {
        "id": whiteboard.id,
        "name": "Board 1",
        "order": whiteboard.order,
        "type": "whiteboard",
        "content": {
            "elements": [{"id": "abc"}],
            "appState": {"viewBackgroundColor": "#fff"},
        },
    }


@pytest.mark.django_db
def test_whiteboard_import_serialized(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    serialized = {
        "id": 999,
        "name": "Imported Board",
        "order": 1,
        "type": "whiteboard",
        "content": {"elements": [{"id": "abc"}]},
    }

    imported = WhiteboardApplicationType().import_serialized(
        workspace,
        serialized,
        ImportExportConfig(include_permission_data=True),
        id_mapping={},
    )

    assert isinstance(imported, Whiteboard)
    assert imported.name == "Imported Board"
    assert imported.workspace_id == workspace.id
    assert imported.content == {"elements": [{"id": "abc"}]}


@pytest.mark.django_db
def test_whiteboard_import_serialized_without_content(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    serialized = {
        "id": 999,
        "name": "Empty Board",
        "order": 1,
        "type": "whiteboard",
        "content": {},
    }

    imported = WhiteboardApplicationType().import_serialized(
        workspace,
        serialized,
        ImportExportConfig(include_permission_data=True),
        id_mapping={},
    )

    assert imported.content == {}
