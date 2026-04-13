import pytest

from baserow.contrib.whiteboard.ws.pages import WhiteboardPageType


@pytest.mark.django_db
def test_whiteboard_page_type_can_add(data_fixture):
    user = data_fixture.create_user()
    whiteboard = data_fixture.create_whiteboard_application(user=user)
    page_type = WhiteboardPageType()

    assert page_type.can_add(user, "ws-id", whiteboard.id) is True


@pytest.mark.django_db
def test_whiteboard_page_type_can_add_non_existing_whiteboard(data_fixture):
    user = data_fixture.create_user()
    page_type = WhiteboardPageType()

    assert page_type.can_add(user, "ws-id", 99999) is False


@pytest.mark.django_db
def test_whiteboard_page_type_can_add_no_whiteboard_id(data_fixture):
    user = data_fixture.create_user()
    page_type = WhiteboardPageType()

    assert page_type.can_add(user, "ws-id", None) is False
    assert page_type.can_add(user, "ws-id", 0) is False


@pytest.mark.django_db
def test_whiteboard_page_type_group_name(data_fixture):
    page_type = WhiteboardPageType()

    assert page_type.get_group_name(whiteboard_id=42) == "whiteboard-42"


@pytest.mark.django_db
def test_whiteboard_page_type_permission_channel_group_name(data_fixture):
    page_type = WhiteboardPageType()

    assert (
        page_type.get_permission_channel_group_name(whiteboard_id=42)
        == "permissions-whiteboard-42"
    )
