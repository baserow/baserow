import json
from unittest.mock import patch

import pytest

from baserow.contrib.builder.theme.service import ThemeService


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.builder.ws.theme.signals.broadcast_to_permitted_users")
def test_theme_updated(mock_broadcast_to_permitted_users, data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)

    ThemeService().update_theme(
        user=user,
        builder=builder,
        primary_color="#ff0000",
    )

    mock_broadcast_to_permitted_users.delay.assert_called_once()
    args = mock_broadcast_to_permitted_users.delay.call_args

    assert args[0][4]["type"] == "theme_updated"
    assert args[0][4]["builder_id"] == builder.id
    assert args[0][4]["properties"] == {"primary_color": "#ff0000"}


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.builder.ws.theme.signals.broadcast_to_permitted_users")
def test_theme_updated_with_page_background_file(
    mock_broadcast_to_permitted_users, data_fixture
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    user_file = data_fixture.create_user_file(is_image=True)

    ThemeService().update_theme(
        user=user,
        builder=builder,
        page_background_file=user_file,
    )

    args = mock_broadcast_to_permitted_users.delay.call_args
    properties = args[0][4]["properties"]
    assert properties["page_background_file"]["name"] == user_file.name
    # The payload is sent to Celery so it must be JSON serializable.
    json.dumps(args[0])
