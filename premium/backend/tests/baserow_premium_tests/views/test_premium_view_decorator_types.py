from django.test.utils import override_settings

import pytest

from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import ViewDecoration
from baserow_premium.license.exceptions import FeaturesNotAvailableError


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_left_border_color_with_premium_license(premium_data_fixture):
    user = premium_data_fixture.create_user(has_active_premium_license=True)
    grid_view = premium_data_fixture.create_grid_view(user=user)

    handler = ViewHandler()
    decoration = handler.create_decoration(
        view=grid_view,
        decorator_type_name="left_border_color",
        value_provider_type_name="",
        value_provider_conf={},
        user=user,
    )

    assert isinstance(decoration, ViewDecoration)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_left_border_color_without_premium_license(premium_data_fixture):
    user = premium_data_fixture.create_user(has_active_premium_license=False)
    grid_view = premium_data_fixture.create_grid_view(user=user)

    handler = ViewHandler()

    with pytest.raises(FeaturesNotAvailableError):
        handler.create_decoration(
            view=grid_view,
            decorator_type_name="left_border_color",
            value_provider_type_name="",
            value_provider_conf={},
            user=user,
        )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_left_border_color_without_premium_license_for_workspace(
    premium_data_fixture, alternative_per_workspace_license_service
):
    user = premium_data_fixture.create_user(has_active_premium_license=True)
    grid_view = premium_data_fixture.create_grid_view(user=user)

    handler = ViewHandler()

    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, [grid_view.table.database.workspace.id]
    )
    handler.create_decoration(
        view=grid_view,
        decorator_type_name="left_border_color",
        value_provider_type_name="",
        value_provider_conf={},
        user=user,
    )

    alternative_per_workspace_license_service.restrict_user_premium_to(user, [0])
    with pytest.raises(FeaturesNotAvailableError):
        handler.create_decoration(
            view=grid_view,
            decorator_type_name="left_border_color",
            value_provider_type_name="",
            value_provider_conf={},
            user=user,
        )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_background_color_with_premium_license(premium_data_fixture):
    user = premium_data_fixture.create_user(has_active_premium_license=True)
    grid_view = premium_data_fixture.create_grid_view(user=user)

    handler = ViewHandler()
    decoration = handler.create_decoration(
        view=grid_view,
        decorator_type_name="background_color",
        value_provider_type_name="",
        value_provider_conf={},
        user=user,
    )

    assert isinstance(decoration, ViewDecoration)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_background_color_without_premium_license(premium_data_fixture):
    user = premium_data_fixture.create_user(has_active_premium_license=False)
    grid_view = premium_data_fixture.create_grid_view(user=user)

    handler = ViewHandler()

    with pytest.raises(FeaturesNotAvailableError):
        handler.create_decoration(
            view=grid_view,
            decorator_type_name="background_color",
            value_provider_type_name="",
            value_provider_conf={},
            user=user,
        )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_background_color_without_premium_license_for_workspace(
    premium_data_fixture, alternative_per_workspace_license_service
):
    user = premium_data_fixture.create_user(has_active_premium_license=True)
    grid_view = premium_data_fixture.create_grid_view(user=user)

    handler = ViewHandler()

    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, [grid_view.table.database.workspace.id]
    )
    handler.create_decoration(
        view=grid_view,
        decorator_type_name="background_color",
        value_provider_type_name="",
        value_provider_conf={},
        user=user,
    )

    alternative_per_workspace_license_service.restrict_user_premium_to(user, [0])
    with pytest.raises(FeaturesNotAvailableError):
        handler.create_decoration(
            view=grid_view,
            decorator_type_name="background_color",
            value_provider_type_name="",
            value_provider_conf={},
            user=user,
        )
