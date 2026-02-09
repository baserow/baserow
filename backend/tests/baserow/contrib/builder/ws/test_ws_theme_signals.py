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
