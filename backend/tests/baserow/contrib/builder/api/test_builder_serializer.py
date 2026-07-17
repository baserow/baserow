"""Test the BuilderSerializer serializer."""

from django.shortcuts import reverse

import pytest


@pytest.fixture()
def builder_fixture(data_fixture):
    """A fixture to help test the BuilderSerializer."""

    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(user=user, builder=builder)

    return {
        "builder": builder,
        "page": page,
        "user": user,
        "token": token,
    }


@pytest.mark.django_db
def test_validate_login_page_id_raises_error_if_shared_page(
    api_client, builder_fixture
):
    """Ensure that only non-shared pages can be used as the login_page."""

    builder = builder_fixture["builder"]

    # Set the builder's page to be the shared page
    shared_page = builder.page_set.get(shared=True)
    response = api_client.patch(
        reverse("api:applications:item", kwargs={"application_id": builder.id}),
        {"login_page_id": shared_page.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {builder_fixture['token']}",
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": {
            "login_page_id": [
                {
                    "code": "invalid_login_page_id",
                    "error": "The login page cannot be a shared page.",
                },
            ],
        },
        "error": "ERROR_REQUEST_BODY_VALIDATION",
    }


@pytest.mark.django_db
def test_login_page_is_saved(api_client, builder_fixture):
    """Ensure that a valid page can be set as the Builder's login_page."""

    builder = builder_fixture["builder"]
    assert builder.login_page is None

    page = builder_fixture["page"]
    response = api_client.patch(
        reverse("api:applications:item", kwargs={"application_id": builder.id}),
        {"login_page_id": page.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {builder_fixture['token']}",
    )

    assert response.status_code == 200
    builder.refresh_from_db()
    assert builder.login_page == page


@pytest.mark.django_db
def test_breakpoints_are_saved(api_client, builder_fixture):
    builder = builder_fixture["builder"]

    response = api_client.patch(
        reverse("api:applications:item", kwargs={"application_id": builder.id}),
        {"mobile_breakpoint": 640, "tablet_breakpoint": 1024},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {builder_fixture['token']}",
    )

    assert response.status_code == 200
    assert response.json()["mobile_breakpoint"] == 640
    assert response.json()["tablet_breakpoint"] == 1024

    builder.refresh_from_db()
    assert builder.mobile_breakpoint == 640
    assert builder.tablet_breakpoint == 1024


@pytest.mark.django_db
def test_breakpoints_must_be_configured_together_and_in_order(
    api_client, builder_fixture
):
    builder = builder_fixture["builder"]
    builder.mobile_breakpoint = None
    builder.tablet_breakpoint = None
    builder.save()

    response = api_client.patch(
        reverse("api:applications:item", kwargs={"application_id": builder.id}),
        {"mobile_breakpoint": 640},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {builder_fixture['token']}",
    )

    assert response.status_code == 400
    assert "mobile_breakpoint" in response.json()["detail"]
    assert "tablet_breakpoint" in response.json()["detail"]

    response = api_client.patch(
        reverse("api:applications:item", kwargs={"application_id": builder.id}),
        {"mobile_breakpoint": 1024, "tablet_breakpoint": 1024},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {builder_fixture['token']}",
    )

    assert response.status_code == 400
    assert "tablet_breakpoint" in response.json()["detail"]
