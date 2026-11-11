from types import SimpleNamespace

from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_404_NOT_FOUND

from baserow.contrib.builder.domains.handler import DomainHandler
from baserow.contrib.builder.domains.service import DomainService
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.core.handler import CoreHandler
from baserow.core.trash.handler import TrashHandler


@pytest.fixture
def published_app(data_fixture):
    user = data_fixture.create_user()
    draft = data_fixture.create_builder_application(user=user)
    published = data_fixture.create_builder_application(workspace=None)
    domain = data_fixture.create_builder_custom_domain(
        builder=draft, published_to=published, domain_name="cached.example.com"
    )
    page = data_fixture.create_builder_page(builder=published)
    element = data_fixture.create_builder_heading_element(page=page)
    data_fixture.create_builder_local_baserow_get_row_data_source(page=page)
    data_fixture.create_notification_workflow_action(page=page, element=element)
    return SimpleNamespace(
        user=user, draft=draft, published=published, domain=domain, page=page
    )


def delete_domain(app):
    DomainService().delete_domain(app.user, app.domain)


def republish(app):
    DomainHandler().publish(app.domain)


def trash_page(app):
    TrashHandler.trash(app.user, app.draft.workspace, app.published, app.page)


def delete_page(app):
    PageHandler().delete_page(app.page)


def rename_domain(app):
    DomainService().update_domain(app.user, app.domain, domain_name="new.example.com")


def trash_application(app):
    CoreHandler().delete_application(app.user, app.draft)


def trash_workspace(app):
    CoreHandler().delete_workspace(
        app.user, CoreHandler().get_workspace_for_update(app.draft.workspace_id)
    )


@pytest.mark.django_db
@pytest.mark.parametrize("endpoint", ["elements", "data_sources", "workflow_actions"])
@pytest.mark.parametrize(
    "unpublish", [delete_domain, republish, trash_page, delete_page]
)
def test_public_page_lists_stop_serving_cached_records_once_unpublished(
    api_client,
    data_fixture,
    django_assert_num_queries,
    django_capture_on_commit_callbacks,
    published_app,
    endpoint,
    unpublish,
):
    url = reverse(
        f"api:builder:domains:list_{endpoint}",
        kwargs={"page_id": published_app.page.id},
    )

    response = api_client.get(url)
    assert response.status_code == HTTP_200_OK
    assert len(response.json()) == 1

    # Cache hits for anonymous visitors stay free of database queries.
    with django_assert_num_queries(0):
        response = api_client.get(url)
    assert response.status_code == HTTP_200_OK

    with django_capture_on_commit_callbacks(execute=True):
        unpublish(published_app)

    response = api_client.get(url)
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_PAGE_DOES_NOT_EXIST"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "unpublish", [delete_domain, rename_domain, trash_application, trash_workspace]
)
def test_public_builder_by_domain_stops_serving_cached_builder_once_unpublished(
    api_client, django_capture_on_commit_callbacks, published_app, unpublish
):
    url = reverse(
        "api:builder:domains:get_builder_by_domain_name",
        kwargs={"domain_name": published_app.domain.domain_name},
    )

    response = api_client.get(url)
    assert response.status_code == HTTP_200_OK
    assert response.json()["id"] == published_app.published.id

    with django_capture_on_commit_callbacks(execute=True):
        unpublish(published_app)

    response = api_client.get(url)
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_BUILDER_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_public_builder_by_domain_serves_the_new_publication_once_republished(
    api_client, django_capture_on_commit_callbacks, published_app
):
    url = reverse(
        "api:builder:domains:get_builder_by_domain_name",
        kwargs={"domain_name": published_app.domain.domain_name},
    )

    response = api_client.get(url)
    assert response.status_code == HTTP_200_OK
    assert response.json()["id"] == published_app.published.id

    with django_capture_on_commit_callbacks(execute=True):
        domain = DomainHandler().publish(published_app.domain)

    response = api_client.get(url)
    assert response.status_code == HTTP_200_OK
    assert response.json()["id"] == domain.published_to_id != published_app.published.id
