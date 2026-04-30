import pytest

from baserow.contrib.whiteboard.exceptions import WhiteboardDoesNotExist
from baserow.contrib.whiteboard.handler import WhiteboardHandler


@pytest.mark.django_db
def test_get_whiteboard_returns_instance(data_fixture):
    whiteboard = data_fixture.create_whiteboard_application()
    fetched = WhiteboardHandler().get_whiteboard(whiteboard.id)
    assert fetched.id == whiteboard.id
    assert fetched.workspace_id == whiteboard.workspace_id


@pytest.mark.django_db
def test_get_whiteboard_raises_when_missing(data_fixture):
    with pytest.raises(WhiteboardDoesNotExist):
        WhiteboardHandler().get_whiteboard(999_999)
