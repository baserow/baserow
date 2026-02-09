from django.test.utils import override_settings

import pytest

from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import FormView
from baserow_premium.license.exceptions import FeaturesNotAvailableError


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_survey_form_without_premium_license(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)

    handler = ViewHandler()

    with pytest.raises(FeaturesNotAvailableError):
        handler.create_view(
            user=user, table=table, type_name="form", name="Form", mode="survey"
        )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_survey_form_with_premium_license(premium_data_fixture):
    user = premium_data_fixture.create_user(has_active_premium_license=True)
    table = premium_data_fixture.create_database_table(user=user)

    handler = ViewHandler()
    handler.create_view(
        user=user, table=table, type_name="form", name="Form", mode="survey"
    )

    assert FormView.objects.all().count() == 1


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_survey_form_with_premium_license_for_workspace(
    premium_data_fixture, alternative_per_workspace_license_service
):
    user = premium_data_fixture.create_user(
        first_name="Test User", has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)

    handler = ViewHandler()

    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, [table.database.workspace.id]
    )
    handler.create_view(
        user=user, table=table, type_name="form", name="Form", mode="survey"
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_survey_form_without_premium_license_for_workspace(
    premium_data_fixture, alternative_per_workspace_license_service
):
    user = premium_data_fixture.create_user(
        first_name="Test User", has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)

    handler = ViewHandler()

    alternative_per_workspace_license_service.restrict_user_premium_to(user, [0])
    with pytest.raises(FeaturesNotAvailableError):
        handler.create_view(
            user=user, table=table, type_name="form", name="Form", mode="survey"
        )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_to_survey_form_without_premium_license(premium_data_fixture):
    user = premium_data_fixture.create_user()
    form = premium_data_fixture.create_form_view(user=user)

    handler = ViewHandler()

    with pytest.raises(FeaturesNotAvailableError):
        handler.update_view(user=user, view=form, mode="survey")


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_existing_survey_form_without_premium_license(premium_data_fixture):
    user = premium_data_fixture.create_user()
    form = premium_data_fixture.create_form_view(user=user, mode="survey")

    handler = ViewHandler()
    # This should succeed because the "survey" value is not provided.
    handler.update_view(user=user, view=form, name="test")

    form.refresh_from_db()
    assert form.name == "test"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_survey_form_with_premium_license(premium_data_fixture):
    user = premium_data_fixture.create_user(has_active_premium_license=True)
    form = premium_data_fixture.create_form_view(user=user)

    handler = ViewHandler()
    handler.update_view(user=user, view=form, mode="survey")

    view = FormView.objects.all().first()
    assert view.mode == "survey"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_survey_form_without_premium_license_for_workspace(
    premium_data_fixture, alternative_per_workspace_license_service
):
    user = premium_data_fixture.create_user()
    form = premium_data_fixture.create_form_view(user=user)

    handler = ViewHandler()

    alternative_per_workspace_license_service.restrict_user_premium_to(user, [0])
    with pytest.raises(FeaturesNotAvailableError):
        handler.update_view(user=user, view=form, mode="survey")


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_survey_form_with_premium_license_for_workspace(
    premium_data_fixture, alternative_per_workspace_license_service
):
    user = premium_data_fixture.create_user(has_active_premium_license=True)
    form = premium_data_fixture.create_form_view(user=user)

    handler = ViewHandler()

    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, [form.table.database.workspace.id]
    )
    handler.update_view(user=user, view=form, mode="survey")

    view = FormView.objects.all().first()
    assert view.mode == "survey"
