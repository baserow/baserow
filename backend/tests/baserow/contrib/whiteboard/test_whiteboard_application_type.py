import json

import pytest

from baserow.contrib.whiteboard.application_types import WhiteboardApplicationType
from baserow.contrib.whiteboard.models import Whiteboard
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig


@pytest.mark.django_db
def test_whiteboard_export_serialized(data_fixture):
    user = data_fixture.create_user()
    whiteboard = data_fixture.create_whiteboard_application(
        name="Whiteboard 1",
        content={"store": {"shapes": []}},
        user=user,
    )
    serialized = WhiteboardApplicationType().export_serialized(
        whiteboard, ImportExportConfig(include_permission_data=True)
    )
    serialized = json.loads(json.dumps(serialized))

    assert serialized == {
        "id": whiteboard.id,
        "name": whiteboard.name,
        "content": {"store": {"shapes": []}},
        "order": whiteboard.order,
        "type": "whiteboard",
    }


@pytest.mark.django_db
def test_whiteboard_export_serialized_empty_content(data_fixture):
    user = data_fixture.create_user()
    whiteboard = data_fixture.create_whiteboard_application(
        name="Empty Whiteboard",
        user=user,
    )
    serialized = WhiteboardApplicationType().export_serialized(
        whiteboard, ImportExportConfig(include_permission_data=True)
    )
    serialized = json.loads(json.dumps(serialized))

    assert serialized["content"] == {}
    assert serialized["type"] == "whiteboard"


@pytest.mark.django_db
def test_whiteboard_import_serialized(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    id_mapping = {}
    serialized = {
        "id": "999",
        "name": "Whiteboard 1",
        "content": {"store": {"shapes": [{"id": "shape:1"}]}},
        "order": 99,
        "type": "whiteboard",
    }

    whiteboard = WhiteboardApplicationType().import_serialized(
        workspace,
        serialized,
        ImportExportConfig(include_permission_data=True),
        id_mapping,
    )

    assert whiteboard.name == "Whiteboard 1"
    assert whiteboard.content == {"store": {"shapes": [{"id": "shape:1"}]}}
    assert whiteboard.order == 99


@pytest.mark.django_db
def test_whiteboard_create_via_core_handler(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    whiteboard = CoreHandler().create_application(
        user,
        workspace,
        type_name="whiteboard",
        name="My Whiteboard",
    )

    assert whiteboard.name == "My Whiteboard"
    assert isinstance(whiteboard.specific, Whiteboard)
    assert whiteboard.specific.content == {}
