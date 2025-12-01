from unittest.mock import patch

import pytest

from baserow.contrib.builder.theme.service import ThemeService
from baserow.core.exceptions import UserNotInWorkspace


@patch("baserow.contrib.builder.theme.service.theme_updated")
@pytest.mark.django_db
def test_theme_updated_signal_sent(theme_updated_mock, data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)

    service = ThemeService()
    service.update_theme(user, builder, primary_color="#f00000ff")

    theme_updated_mock.send.assert_called_once_with(
        service,
        builder=builder,
        user=user,
        properties={
            "primary_color": "#f00000ff",
        },
    )


@pytest.mark.django_db
def test_update_theme_user_not_in_workspace(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application()

    with pytest.raises(UserNotInWorkspace):
        ThemeService().update_theme(user, builder, primary_color="#f00000ff")


@pytest.mark.django_db
def test_update_theme_updated(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)

    builder = ThemeService().update_theme(
        user, builder, primary_color="#f00000ff", heading_1_font_size=42
    )

    assert builder.colorthemeconfigblock.primary_color == "#f00000ff"
    assert builder.typographythemeconfigblock.heading_1_font_size == 42
