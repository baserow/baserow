import pytest

from baserow.contrib.whiteboard.exceptions import WhiteboardDoesNotExist
from baserow.contrib.whiteboard.handler import WhiteboardHandler


@pytest.mark.django_db
def test_get_whiteboard(data_fixture):
    user = data_fixture.create_user()
    whiteboard = data_fixture.create_whiteboard_application(
        user=user, content={"test": True}
    )

    result = WhiteboardHandler().get_whiteboard(whiteboard.id)

    assert result.id == whiteboard.id
    assert result.content == {"test": True}
    assert result.workspace is not None


@pytest.mark.django_db
def test_get_whiteboard_not_found():
    with pytest.raises(WhiteboardDoesNotExist):
        WhiteboardHandler().get_whiteboard(99999)


@pytest.mark.django_db
def test_get_whiteboard_with_custom_queryset(data_fixture):
    user = data_fixture.create_user()
    whiteboard = data_fixture.create_whiteboard_application(user=user)

    from baserow.contrib.whiteboard.models import Whiteboard

    qs = Whiteboard.objects.filter(id=whiteboard.id)
    result = WhiteboardHandler().get_whiteboard(whiteboard.id, base_queryset=qs)

    assert result.id == whiteboard.id


@pytest.mark.django_db
def test_get_whiteboard_with_empty_queryset(data_fixture):
    user = data_fixture.create_user()
    whiteboard = data_fixture.create_whiteboard_application(user=user)

    from baserow.contrib.whiteboard.models import Whiteboard

    qs = Whiteboard.objects.none()

    with pytest.raises(WhiteboardDoesNotExist):
        WhiteboardHandler().get_whiteboard(whiteboard.id, base_queryset=qs)
