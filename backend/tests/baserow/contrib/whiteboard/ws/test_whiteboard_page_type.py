import pytest

from baserow.contrib.whiteboard.ws.pages import WhiteboardPageType


@pytest.mark.django_db
def test_can_add_returns_true_for_workspace_member(data_fixture):
    user = data_fixture.create_user()
    whiteboard = data_fixture.create_whiteboard_application(user=user)

    page_type = WhiteboardPageType()
    assert page_type.can_add(user, "ws-1", whiteboard.id) is True


@pytest.mark.django_db
def test_can_add_returns_false_for_non_member(data_fixture):
    user = data_fixture.create_user()
    whiteboard = data_fixture.create_whiteboard_application()

    page_type = WhiteboardPageType()
    assert page_type.can_add(user, "ws-1", whiteboard.id) is False


@pytest.mark.django_db
def test_can_add_returns_false_when_whiteboard_does_not_exist(data_fixture):
    user = data_fixture.create_user()
    page_type = WhiteboardPageType()
    assert page_type.can_add(user, "ws-1", 999_999) is False


def test_can_add_returns_false_without_whiteboard_id():
    page_type = WhiteboardPageType()
    assert page_type.can_add(None, "ws-1", None) is False


def test_get_group_name():
    assert WhiteboardPageType().get_group_name(whiteboard_id=42) == "whiteboard-42"


def test_get_permission_channel_group_name():
    assert (
        WhiteboardPageType().get_permission_channel_group_name(whiteboard_id=42)
        == "permissions-whiteboard-42"
    )
