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
