"""Test the BuilderSerializer serializer."""

from django.shortcuts import reverse

import pytest

from baserow.contrib.builder.models import (
    MAX_BUILDER_BREAKPOINT,
    MIN_BUILDER_BREAKPOINT,
)


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
def test_builder_application_can_be_created_without_breakpoints(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    response = api_client.post(
        reverse("api:applications:list", kwargs={"workspace_id": workspace.id}),
        {"name": "Test builder", "type": "builder"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 200
    assert response.json()["breakpoints"] == {"mobile": 640, "tablet": 1024}


@pytest.mark.django_db
def test_builder_application_cannot_be_created_with_empty_breakpoints(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    response = api_client.post(
        reverse("api:applications:list", kwargs={"workspace_id": workspace.id}),
        {"name": "Test builder", "type": "builder", "breakpoints": {}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 400
    assert set(response.json()["detail"]["breakpoints"]) == {"mobile", "tablet"}


@pytest.mark.django_db
def test_breakpoints_are_saved(api_client, builder_fixture):
    builder = builder_fixture["builder"]

    response = api_client.patch(
        reverse("api:applications:item", kwargs={"application_id": builder.id}),
        {"breakpoints": {"mobile": 700, "tablet": 1100, "laptop": 1280}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {builder_fixture['token']}",
    )

    assert response.status_code == 200
    assert response.json()["breakpoints"] == {
        "mobile": 700,
        "tablet": 1100,
        "laptop": 1280,
    }

    builder.refresh_from_db()
    assert builder.breakpoints == {"mobile": 700, "tablet": 1100, "laptop": 1280}


@pytest.mark.django_db
def test_breakpoints_are_coerced_to_integers(api_client, builder_fixture):
    builder = builder_fixture["builder"]

    response = api_client.patch(
        reverse("api:applications:item", kwargs={"application_id": builder.id}),
        {"breakpoints": {"mobile": "700", "tablet": "1100"}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {builder_fixture['token']}",
    )

    assert response.status_code == 200
    assert response.json()["breakpoints"] == {"mobile": 700, "tablet": 1100}

    builder.refresh_from_db()
    assert builder.breakpoints == {"mobile": 700, "tablet": 1100}


@pytest.mark.django_db
def test_breakpoints_can_use_supported_range_boundaries(api_client, builder_fixture):
    builder = builder_fixture["builder"]
    breakpoints = {
        "mobile": MIN_BUILDER_BREAKPOINT,
        "tablet": MAX_BUILDER_BREAKPOINT,
    }

    response = api_client.patch(
        reverse("api:applications:item", kwargs={"application_id": builder.id}),
        {"breakpoints": breakpoints},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {builder_fixture['token']}",
    )

    assert response.status_code == 200
    assert response.json()["breakpoints"] == breakpoints

    builder.refresh_from_db()
    assert builder.breakpoints == breakpoints


@pytest.mark.django_db
def test_legacy_breakpoints_can_be_updated(api_client, builder_fixture):
    builder = builder_fixture["builder"]
    builder.breakpoints = {"mobile": 500, "tablet": 768}
    builder.save()

    response = api_client.patch(
        reverse("api:applications:item", kwargs={"application_id": builder.id}),
        {"breakpoints": {"mobile": 700, "tablet": 1100}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {builder_fixture['token']}",
    )

    assert response.status_code == 200
    assert response.json()["breakpoints"] == {"mobile": 700, "tablet": 1100}


@pytest.mark.django_db
def test_legacy_breakpoints_are_preserved_when_omitted_from_a_partial_update(
    api_client, builder_fixture
):
    builder = builder_fixture["builder"]
    builder.breakpoints = {"mobile": 500, "tablet": 768}
    builder.save()

    response = api_client.patch(
        reverse("api:applications:item", kwargs={"application_id": builder.id}),
        {"name": "Updated builder"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {builder_fixture['token']}",
    )

    assert response.status_code == 200
    assert response.json()["breakpoints"] == {"mobile": 500, "tablet": 768}

    builder.refresh_from_db()
    assert builder.breakpoints == {"mobile": 500, "tablet": 768}


@pytest.mark.django_db
def test_breakpoints_must_include_mobile_and_tablet_in_order(
    api_client, builder_fixture
):
    builder = builder_fixture["builder"]

    response = api_client.patch(
        reverse("api:applications:item", kwargs={"application_id": builder.id}),
        {"breakpoints": {"mobile": 640}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {builder_fixture['token']}",
    )

    assert response.status_code == 400
    assert "mobile" in response.json()["detail"]["breakpoints"]
    assert "tablet" in response.json()["detail"]["breakpoints"]

    response = api_client.patch(
        reverse("api:applications:item", kwargs={"application_id": builder.id}),
        {"breakpoints": {"mobile": 1024, "tablet": 1024}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {builder_fixture['token']}",
    )

    assert response.status_code == 400
    assert "tablet" in response.json()["detail"]["breakpoints"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("breakpoints", "invalid_breakpoint"),
    [
        ({"mobile": MIN_BUILDER_BREAKPOINT - 1, "tablet": 1024}, "mobile"),
        ({"mobile": 640, "tablet": MAX_BUILDER_BREAKPOINT + 1}, "tablet"),
    ],
)
def test_breakpoints_must_be_within_supported_range(
    api_client, builder_fixture, breakpoints, invalid_breakpoint
):
    builder = builder_fixture["builder"]

    response = api_client.patch(
        reverse("api:applications:item", kwargs={"application_id": builder.id}),
        {"breakpoints": breakpoints},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {builder_fixture['token']}",
    )

    assert response.status_code == 400
    assert invalid_breakpoint in response.json()["detail"]["breakpoints"]
