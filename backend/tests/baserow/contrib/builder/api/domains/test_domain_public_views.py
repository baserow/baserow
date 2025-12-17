from unittest.mock import ANY, MagicMock, patch

from django.test.utils import override_settings
from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_202_ACCEPTED,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.api.user_files.serializers import UserFileSerializer
from baserow.contrib.builder.data_sources.exceptions import DataSourceDoesNotExist
from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.database.views.models import SORT_ORDER_ASC
from baserow.core.exceptions import PermissionException
from baserow.core.formula import BaserowFormulaObject
from baserow.core.formula.field import BASEROW_FORMULA_VERSION_INITIAL
from baserow.core.formula.types import BASEROW_FORMULA_MODE_SIMPLE
from baserow.core.models import Workspace
from baserow.core.services.exceptions import (
    DoesNotExist,
    InvalidContextContentDispatchException,
    InvalidContextDispatchException,
    ServiceImproperlyConfiguredDispatchException,
    UnexpectedDispatchException,
)
from baserow.core.user_sources.user_source_user import UserSourceUser


@pytest.fixture
def data_source_element_roles_fixture(data_fixture):
    """
    A fixture to help test the DispatchDataSourcesView view using Elements
    and user roles.
    """

    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    builder_to = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(builder=builder, published_to=builder_to)
    public_page = data_fixture.create_builder_page(builder=builder_to)

    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("Color", "text"),
        ],
        rows=[
            ["Apple", "Red"],
            ["Banana", "Yellow"],
            ["Cherry", "Purple"],
        ],
    )

    return {
        "page": public_page,
        "user": user,
        "table": table,
        "fields": fields,
        "rows": rows,
        "builder_to": builder_to,
    }


@pytest.fixture
def data_source_fixture(data_fixture):
    """A fixture to help test views that rely on a data source."""

    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("Color", "text"),
        ],
        rows=[
            ["Apple", "Red"],
            ["Banana", "Yellow"],
            ["Cherry", "Purple"],
        ],
    )
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)

    return {
        "user": user,
        "token": token,
        "page": page,
        "integration": integration,
        "table": table,
        "rows": rows,
        "fields": fields,
    }


@pytest.mark.django_db
def test_get_public_builder_by_domain_name(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    favicon_file = data_fixture.create_user_file(original_extension=".png")
    builder_to = data_fixture.create_builder_application(
        workspace=None,
        favicon_file=favicon_file,
    )
    page = data_fixture.create_builder_page(user=user, builder=builder_to)
    page2 = data_fixture.create_builder_page(user=user, builder=builder_to)

    domain = data_fixture.create_builder_custom_domain(
        domain_name="xyztest.getbaserow.io", published_to=builder_to
    )

    url = reverse(
        "api:builder:domains:get_builder_by_domain_name",
        kwargs={"domain_name": "xyztest.getbaserow.io"},
    )

    # Anonymous request
    response = api_client.get(
        url,
        format="json",
    )

    response_json = response.json()

    assert response.status_code == HTTP_200_OK
    assert response_json["theme"]["primary_color"] == "#5190efff"

    del response_json["theme"]  # We are not testing the theme response here.

    assert builder_to.page_set.filter(shared=True).count() == 1

    shared_page = builder_to.shared_page
    workspace = Workspace.objects.get()

    assert (
        response_json["favicon_file"]
        == UserFileSerializer(builder_to.favicon_file).data
    )
    assert response_json["login_page_id"] is None
    assert response_json["workspace"] == {
        "generative_ai_models_enabled": {},
        "id": workspace.id,
        "name": workspace.name,
        "licenses": [],
    }
    assert response_json["pages"] == [
        {
            "id": shared_page.id,
            "name": "__shared__",
            "path": "__shared__",
            "path_params": [],
            "query_params": [],
            "shared": True,
            "visibility": Page.VISIBILITY_TYPES.ALL.value,
            "role_type": Page.ROLE_TYPES.ALLOW_ALL.value,
            "roles": [],
        },
        {
            "id": page.id,
            "name": page.name,
            "path": page.path,
            "path_params": [],
            "query_params": [],
            "shared": False,
            "visibility": Page.VISIBILITY_TYPES.ALL.value,
            "role_type": Page.ROLE_TYPES.ALLOW_ALL.value,
            "roles": [],
        },
        {
            "id": page2.id,
            "name": page2.name,
            "path": page2.path,
            "path_params": [],
            "query_params": [],
            "shared": False,
            "visibility": Page.VISIBILITY_TYPES.ALL.value,
            "role_type": Page.ROLE_TYPES.ALLOW_ALL.value,
            "roles": [],
        },
    ]

    # Even if I'm authenticated I should be able to see it.
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_get_builder_missing_domain_name(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    page2 = data_fixture.create_builder_page(builder=page.builder, user=user)

    domain = data_fixture.create_builder_custom_domain(
        domain_name="test.getbaserow.io", published_to=page.builder
    )

    url = reverse(
        "api:builder:domains:get_builder_by_domain_name",
        kwargs={"domain_name": "notexists.getbaserow.io"},
    )
    response = api_client.get(
        url,
        format="json",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_BUILDER_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_get_non_public_builder(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    data_fixture.create_builder_page(builder=page.builder, user=user)
    data_fixture.create_builder_custom_domain(
        domain_name="notpublic.getbaserow.io", builder=page.builder
    )

    url = reverse(
        "api:builder:domains:get_builder_by_domain_name",
        kwargs={"domain_name": "notpublic.getbaserow.io"},
    )
    response = api_client.get(
        url,
        format="json",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_BUILDER_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_get_public_builder_by_id(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    favicon_file = data_fixture.create_user_file(original_extension=".png")
    page = data_fixture.create_builder_page(user=user)
    page.builder.favicon_file = favicon_file
    page.builder.save()
    page2 = data_fixture.create_builder_page(builder=page.builder, user=user)

    url = reverse(
        "api:builder:domains:get_builder_by_id",
        kwargs={"builder_id": page.builder.id},
    )

    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()

    assert response.status_code == HTTP_200_OK
    assert response_json["theme"]["primary_color"] == "#5190efff"

    del response_json["theme"]  # We are not testing the theme response here.

    assert page.builder.page_set.filter(shared=True).count() == 1

    shared_page = page.builder.shared_page

    assert (
        response_json["favicon_file"]
        == UserFileSerializer(page.builder.favicon_file).data
    )
    assert response_json["login_page_id"] is None
    assert response_json["workspace"] == {
        "generative_ai_models_enabled": {},
        "id": page.builder.workspace.id,
        "name": page.builder.workspace.name,
        "licenses": [],
    }
    assert response_json["pages"] == [
        {
            "id": shared_page.id,
            "name": "__shared__",
            "path": "__shared__",
            "path_params": [],
            "query_params": [],
            "shared": True,
            "visibility": Page.VISIBILITY_TYPES.ALL.value,
            "role_type": Page.ROLE_TYPES.ALLOW_ALL.value,
            "roles": [],
        },
        {
            "id": page.id,
            "name": page.name,
            "path": page.path,
            "path_params": [],
            "query_params": [],
            "shared": False,
            "visibility": Page.VISIBILITY_TYPES.ALL.value,
            "role_type": Page.ROLE_TYPES.ALLOW_ALL.value,
            "roles": [],
        },
        {
            "id": page2.id,
            "name": page2.name,
            "path": page2.path,
            "path_params": [],
            "query_params": [],
            "shared": False,
            "visibility": Page.VISIBILITY_TYPES.ALL.value,
            "role_type": Page.ROLE_TYPES.ALLOW_ALL.value,
            "roles": [],
        },
    ]


@pytest.mark.django_db
def test_get_public_builder_by_id_other_user(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    other_user, other_token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    page2 = data_fixture.create_builder_page(builder=page.builder, user=user)

    url = reverse(
        "api:builder:domains:get_builder_by_id",
        kwargs={"builder_id": page.builder.id},
    )

    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {other_token}",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.jobs.handler.run_async_job")
def test_publish_builder(mock_run_async_job, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder_from = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(builder=builder_from, user=user)
    page2 = data_fixture.create_builder_page(builder=builder_from, user=user)

    domain = data_fixture.create_builder_custom_domain(
        domain_name="test.getbaserow.io", builder=builder_from
    )

    url = reverse(
        "api:builder:domains:publish",
        kwargs={"domain_id": domain.id},
    )
    response = api_client.post(
        url,
        {"domain_id": domain.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()

    assert response.status_code == HTTP_202_ACCEPTED

    mock_run_async_job.delay.assert_called_once()
    args = mock_run_async_job.delay.call_args
    assert args[0][0] == response_json["id"]


@pytest.mark.django_db
def test_get_elements_of_public_builder(api_client, data_fixture):
    user = data_fixture.create_user()
    builder_from = data_fixture.create_builder_application(user=user)
    builder_to = data_fixture.create_builder_application(user=user, workspace=None)
    page = data_fixture.create_builder_page(builder=builder_to, user=user)
    element1 = data_fixture.create_builder_heading_element(page=page)
    element2 = data_fixture.create_builder_heading_element(page=page)
    element3 = data_fixture.create_builder_text_element(page=page)

    domain = data_fixture.create_builder_custom_domain(
        domain_name="test.getbaserow.io",
        published_to=page.builder,
        builder=builder_from,
    )

    url = reverse(
        "api:builder:domains:list_elements",
        kwargs={"page_id": page.id},
    )
    response = api_client.get(
        url,
        format="json",
    )
    response_json = response.json()

    expected_item = {
        "id": element1.id,
        "page_id": page.id,
        "type": "heading",
        "order": "1.00000000000000000000",
        "parent_element_id": None,
        "place_in_container": None,
        "css_classes": "",
        "visibility": "all",
        "visibility_condition": {"formula": "", "mode": "simple", "version": "0.1"},
        "styles": {},
        "style_border_top_color": "border",
        "style_border_top_size": 0,
        "style_padding_top": 10,
        "style_margin_top": 0,
        "style_border_bottom_color": "border",
        "style_border_bottom_size": 0,
        "style_padding_bottom": 10,
        "style_margin_bottom": 0,
        "style_border_left_color": "border",
        "style_border_left_size": 0,
        "style_padding_left": 20,
        "style_margin_left": 0,
        "style_border_right_color": "border",
        "style_border_right_size": 0,
        "style_padding_right": 20,
        "style_margin_right": 0,
        "style_background_radius": 0,
        "style_border_radius": 0,
        "style_background": "none",
        "style_background_color": "#ffffffff",
        "style_background_file": None,
        "style_background_mode": "fill",
        "style_width": "normal",
        "style_width_child": "normal",
        "role_type": "allow_all",
        "roles": [],
        "value": BaserowFormulaObject(
            version=BASEROW_FORMULA_VERSION_INITIAL,
            mode=BASEROW_FORMULA_MODE_SIMPLE,
            formula="",
        ),
        "level": 1,
    }

    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 3
    # Test the structure of the first item to ensure the expected keys exist
    assert response_json[0] == expected_item


@pytest.mark.django_db
def test_get_elements_of_public_builder_with_deactivated(api_client, data_fixture):
    user = data_fixture.create_user()
    builder_from = data_fixture.create_builder_application(user=user)
    builder_to = data_fixture.create_builder_application(user=user, workspace=None)
    page = data_fixture.create_builder_page(builder=builder_to, user=user)
    element1 = data_fixture.create_builder_heading_element(page=page)
    element2 = data_fixture.create_builder_heading_element(page=page)
    element3 = data_fixture.create_builder_text_element(page=page)

    element_type = element3.get_type()

    prev_is_deactivated = element_type.is_deactivated
    element_type.is_deactivated = lambda x: True

    domain = data_fixture.create_builder_custom_domain(
        domain_name="test.getbaserow.io",
        published_to=page.builder,
        builder=builder_from,
    )

    url = reverse(
        "api:builder:domains:list_elements",
        kwargs={"page_id": page.id},
    )
    response = api_client.get(
        url,
        format="json",
    )
    response_json = response.json()

    element_type.is_deactivated = prev_is_deactivated

    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 2


@pytest.mark.django_db
def test_get_elements_of_public_builder_permission_denied(api_client, data_fixture):
    user = data_fixture.create_user()
    builder_from = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(builder=builder_from, user=user)
    element1 = data_fixture.create_builder_heading_element(page=page)

    url = reverse(
        "api:builder:domains:list_elements",
        kwargs={"page_id": page.id},
    )
    response = api_client.get(
        url,
        format="json",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_get_data_source_of_public_builder(api_client, data_fixture):
    user = data_fixture.create_user()
    builder_from = data_fixture.create_builder_application(user=user)
    builder_to = data_fixture.create_builder_application(user=user, workspace=None)
    page = data_fixture.create_builder_page(builder=builder_to, user=user)
    data_source1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )
    data_source2 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )
    data_source3 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )

    domain = data_fixture.create_builder_custom_domain(
        domain_name="test.getbaserow.io",
        published_to=page.builder,
        builder=builder_from,
    )

    url = reverse(
        "api:builder:domains:list_data_sources",
        kwargs={"page_id": page.id},
    )
    response = api_client.get(
        url,
        format="json",
    )

    response_json = response.json()

    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 3


@pytest.mark.django_db
def test_get_data_source_of_public_builder_permission_denied(api_client, data_fixture):
    user = data_fixture.create_user()
    builder_from = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(builder=builder_from, user=user)
    data_source1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )

    url = reverse(
        "api:builder:domains:list_data_sources",
        kwargs={"page_id": page.id},
    )
    response = api_client.get(
        url,
        format="json",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_ask_public_builder_domain_exists(api_client, data_fixture):
    user = data_fixture.create_user()
    builder_from = data_fixture.create_builder_application(user=user)
    builder_to = data_fixture.create_builder_application(user=user, workspace=None)
    data_fixture.create_builder_custom_domain(
        domain_name="test.getbaserow.io",
        published_to=builder_to,
        builder=builder_from,
    )
    data_fixture.create_builder_custom_domain(
        domain_name="another-domain.com",
    )

    url = reverse("api:builder:domains:ask_exists")
    response = api_client.get(url)
    assert response.status_code == 404

    url = reverse("api:builder:domains:ask_exists") + "?domain="
    response = api_client.get(url)
    assert response.status_code == 404

    url = reverse("api:builder:domains:ask_exists") + "?domain=nothing"
    response = api_client.get(url)
    assert response.status_code == 404

    url = reverse("api:builder:domains:ask_exists") + "?domain=nothing.com"
    response = api_client.get(url)
    assert response.status_code == 404

    url = reverse("api:builder:domains:ask_exists") + "?domain=test2.getbaserow.io"
    response = api_client.get(url)
    assert response.status_code == 404

    url = reverse("api:builder:domains:ask_exists") + "?domain=another-domain.com"
    response = api_client.get(url)
    assert response.status_code == 404

    url = reverse("api:builder:domains:ask_exists") + "?domain=test.getbaserow.io"
    response = api_client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
@override_settings(
    PUBLIC_BACKEND_HOSTNAME="backend.localhost",
    PUBLIC_WEB_FRONTEND_HOSTNAME="web-frontend.localhost",
)
def test_ask_public_builder_domain_exists_with_public_backend_and_web_frontend_domains(
    api_client, data_fixture
):
    url = reverse("api:builder:domains:ask_exists") + "?domain=localhost"
    response = api_client.get(url)
    assert response.status_code == 404

    url = reverse("api:builder:domains:ask_exists") + "?domain=backend.localhost"
    response = api_client.get(url)
    assert response.status_code == 200

    url = reverse("api:builder:domains:ask_exists") + "?domain=web-frontend.localhost"
    response = api_client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
@override_settings(
    PUBLIC_BACKEND_HOSTNAME="backend.localhost",
    PUBLIC_WEB_FRONTEND_HOSTNAME="web-frontend.localhost",
    EXTRA_PUBLIC_BACKEND_HOSTNAMES=["extra1.localhost", "extra2.localhost"],
    EXTRA_PUBLIC_WEB_FRONTEND_HOSTNAMES=["extra1.localhost", "extra2.localhost"],
)
def test_ask_public_builder_domain_exists_with_extra_public_urls(api_client):
    # Should reject unknown domain
    url = reverse("api:builder:domains:ask_exists") + "?domain=unknown.localhost"
    response = api_client.get(url)
    assert response.status_code == 404

    # Should accept main backend hostname
    url = reverse("api:builder:domains:ask_exists") + "?domain=backend.localhost"
    response = api_client.get(url)
    assert response.status_code == 200

    # Should accept main web-frontend hostname
    url = reverse("api:builder:domains:ask_exists") + "?domain=web-frontend.localhost"
    response = api_client.get(url)
    assert response.status_code == 200

    # Should accept first extra hostname
    url = reverse("api:builder:domains:ask_exists") + "?domain=extra1.localhost"
    response = api_client.get(url)
    assert response.status_code == 200

    # Should accept second extra hostname
    url = reverse("api:builder:domains:ask_exists") + "?domain=extra2.localhost"
    response = api_client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
@patch("baserow.contrib.builder.api.domains.public_views.BuilderDispatchContext")
@patch(
    "baserow.contrib.builder.api.domains.public_views.DataSourceService.dispatch_data_source"
)
@patch(
    "baserow.contrib.builder.api.domains.public_views.DataSourceHandler.get_data_source"
)
def test_public_dispatch_data_source_view(
    mock_get_data_source,
    mock_dispatch_data_source,
    mock_builder_dispatch_context,
    api_client,
):
    """
    Test the PublicDispatchDataSourceView endpoint.

    Ensure that the field_names are computed to secure the backend.
    """

    mock_data_source = MagicMock()
    mock_get_data_source.return_value = mock_data_source

    mock_response = {}
    mock_dispatch_data_source.return_value = mock_response

    mock_dispatch_context = MagicMock()
    mock_builder_dispatch_context.return_value = mock_dispatch_context

    mock_data_source_id = 100
    url = reverse(
        "api:builder:domains:public_dispatch",
        kwargs={"data_source_id": mock_data_source_id},
    )
    response = api_client.post(url)

    assert response.status_code == 200
    assert response.json() == mock_response
    mock_get_data_source.assert_called_once_with(str(mock_data_source_id))
    mock_builder_dispatch_context.assert_called_once_with(
        ANY,
        mock_data_source.page,
        only_expose_public_allowed_properties=True,
    )
    mock_dispatch_data_source.assert_called_once_with(
        ANY, mock_data_source, mock_dispatch_context
    )


@pytest.mark.django_db
@patch(
    "baserow.contrib.builder.api.domains.public_views.DataSourceService.dispatch_page_data_sources"
)
@patch("baserow.contrib.builder.api.domains.public_views.BuilderDispatchContext")
@patch("baserow.contrib.builder.api.domains.public_views.PageHandler.get_page")
def test_public_dispatch_data_sources_view(
    mock_get_page,
    mock_builder_dispatch_context,
    mock_dispatch_page_data_sources,
    api_client,
):
    """
    Test the PublicDispatchDataSourcesView endpoint.

    Ensure that the field_names are computed to secure the backend.
    """

    mock_page = MagicMock()
    mock_get_page.return_value = mock_page

    mock_dispatch_context = MagicMock()
    mock_builder_dispatch_context.return_value = mock_dispatch_context

    mock_service_contents = {"101": "mock_content"}
    mock_dispatch_page_data_sources.return_value = mock_service_contents

    mock_page_id = 100
    url = reverse(
        "api:builder:domains:public_dispatch_all", kwargs={"page_id": mock_page_id}
    )
    response = api_client.post(url)

    assert response.status_code == 200
    assert response.json() == mock_service_contents
    mock_get_page.assert_called_once_with(mock_page_id)
    mock_builder_dispatch_context.assert_called_once_with(
        ANY, mock_page, only_expose_public_allowed_properties=True
    )
    mock_dispatch_page_data_sources.assert_called_once_with(
        ANY, mock_page, mock_dispatch_context
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "expected_exception,error,detail",
    [
        (
            DataSourceDoesNotExist,
            "ERROR_DATA_SOURCE_DOES_NOT_EXIST",
            "The requested data_source does not exist.",
        ),
        (
            ServiceImproperlyConfiguredDispatchException,
            "ERROR_SERVICE_IMPROPERLY_CONFIGURED",
            "Exception content",
        ),
        (
            InvalidContextDispatchException,
            "ERROR_SERVICE_INVALID_DISPATCH_CONTEXT",
            "Exception content",
        ),
        (
            InvalidContextContentDispatchException,
            "ERROR_SERVICE_INVALID_DISPATCH_CONTEXT_CONTENT",
            "Exception content",
        ),
        (
            UnexpectedDispatchException,
            "ERROR_SERVICE_UNEXPECTED_DISPATCH_ERROR",
            "Exception content",
        ),
        (
            DoesNotExist,
            "ERROR_DATA_SOURCE_DOES_NOT_EXIST",
            "The requested data does not exist.",
        ),
        (
            PermissionException,
            "PERMISSION_DENIED",
            "You don't have the required permission to execute this operation.",
        ),
    ],
)
@patch(
    "baserow.contrib.builder.api.domains.public_views.DataSourceService.dispatch_page_data_sources"
)
@patch("baserow.contrib.builder.api.domains.public_views.BuilderDispatchContext")
@patch("baserow.contrib.builder.api.domains.public_views.PageHandler.get_page")
def test_public_dispatch_data_sources_view_returns_error(
    mock_get_page,
    mock_builder_dispatch_context,
    mock_dispatch_page_data_sources,
    api_client,
    expected_exception,
    error,
    detail,
):
    """
    Test the PublicDispatchDataSourcesView endpoint.

    Ensure that exceptions are handled and returned correctly.
    """

    mock_page = MagicMock()
    mock_get_page.return_value = mock_page

    mock_dispatch_context = MagicMock()
    mock_builder_dispatch_context.return_value = mock_dispatch_context

    mock_service_contents = {"101": expected_exception("Exception content")}
    mock_dispatch_page_data_sources.return_value = mock_service_contents

    mock_page_id = 100
    url = reverse(
        "api:builder:domains:public_dispatch_all", kwargs={"page_id": mock_page_id}
    )
    response = api_client.post(url)

    assert response.status_code == 200
    assert response.json() == {
        "101": {
            "_error": error,
            "detail": detail,
        }
    }
    mock_get_page.assert_called_once_with(mock_page_id)
    mock_builder_dispatch_context.assert_called_once_with(
        ANY, mock_page, only_expose_public_allowed_properties=True
    )
    mock_dispatch_page_data_sources.assert_called_once_with(
        ANY, mock_page, mock_dispatch_context
    )


@pytest.fixture
def user_source_user_fixture(data_fixture):
    """A fixture to provide a user source user."""

    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)

    user_source, _ = data_fixture.create_user_table_and_role(
        user,
        builder,
        "foo_user_role",
        integration=integration,
    )
    user_source_user = UserSourceUser(
        user_source, None, 1, "foo_username", "foo@bar.com", role="foo_user_role"
    )
    user_source_user_token = user_source_user.get_refresh_token().access_token

    return {
        "user": user,
        "page": page,
        "builder": builder,
        "workspace": workspace,
        "integration": integration,
        "user_source_user_token": user_source_user_token,
    }


@pytest.mark.django_db
def test_public_dispatch_data_source_view_returns_all_fields(
    data_fixture,
    api_client,
    user_source_user_fixture,
):
    """
    Test the PublicDispatchDataSourceView endpoint.

    Ensure all fields are returned as long as they're required by an element.
    """

    user = user_source_user_fixture["user"]
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Food", "text"),
            ("Spiciness", "number"),
        ],
        rows=[
            ["Paneer Tikka", 5],
            ["Gobi Manchurian", 8],
        ],
    )
    page = user_source_user_fixture["page"]
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=user,
        page=page,
        integration=user_source_user_fixture["integration"],
        table=table,
    )
    data_fixture.create_builder_table_element(
        user=user,
        page=page,
        data_source=data_source,
        fields=[
            {
                "name": "FieldA",
                "type": "text",
                "config": {"value": f"get('current_record.field_{fields[0].id}')"},
            },
            {
                "name": "FieldB",
                "type": "text",
                "config": {"value": f"get('current_record.field_{fields[1].id}')"},
            },
        ],
    )

    builder = user_source_user_fixture["builder"]
    builder.workspace = None
    builder.save()
    data_fixture.create_builder_custom_domain(published_to=builder)

    url = reverse(
        "api:builder:domains:public_dispatch",
        kwargs={"data_source_id": data_source.id},
    )
    user_token = user_source_user_fixture["user_source_user_token"]

    response = api_client.post(url, HTTP_AUTHORIZATION=f"JWT {user_token}")

    assert response.status_code == 200
    assert response.json() == {
        "has_next_page": False,
        "results": [
            {
                "id": rows[0].id,
                fields[0].name: "Paneer Tikka",
                fields[1].name: 5,
            },
            {
                "id": rows[1].id,
                fields[0].name: "Gobi Manchurian",
                fields[1].name: 8,
            },
        ],
    }


@pytest.mark.django_db
def test_public_dispatch_data_source_view_returns_some_fields(
    data_fixture,
    api_client,
    user_source_user_fixture,
):
    """
    Test the PublicDispatchDataSourceView endpoint.

    Ensure only some fields are returned; only those used by an element in
    the page are returned.
    """

    user = user_source_user_fixture["user"]
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Food", "text"),
            ("Spiciness", "number"),
        ],
        rows=[
            ["Paneer Tikka", 5],
            ["Gobi Manchurian", 8],
        ],
    )
    page = user_source_user_fixture["page"]
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=user,
        page=page,
        integration=user_source_user_fixture["integration"],
        table=table,
    )
    data_fixture.create_builder_heading_element(
        page=page,
        value=f"get('data_source.{data_source.id}.*.field_{fields[0].id}')",
    )

    builder = user_source_user_fixture["builder"]
    builder.workspace = None
    builder.save()
    data_fixture.create_builder_custom_domain(published_to=builder)

    url = reverse(
        "api:builder:domains:public_dispatch",
        kwargs={"data_source_id": data_source.id},
    )
    user_token = user_source_user_fixture["user_source_user_token"]
    response = api_client.post(url, HTTP_AUTHORIZATION=f"JWT {user_token}")

    assert response.status_code == 200
    # Ensure only "field_1" is returned since it is used in the heading element.
    # The "field_2" field should never appear in the result, since it isn't
    # used in the page by any elements.
    assert response.json() == {
        "has_next_page": False,
        "results": [
            {
                fields[0].name: "Paneer Tikka",
            },
            {
                fields[0].name: "Gobi Manchurian",
            },
        ],
    }


@pytest.mark.django_db
def test_public_dispatch_data_sources_get_row_no_elements(
    api_client, data_fixture, user_source_user_fixture
):
    """
    Test the DispatchDataSourcesView endpoint when using a Data Source type
    of Get Row.

    If the page has zero elements, the API response should not contain any
    field specific data.
    """

    user = user_source_user_fixture["user"]
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("Color", "text"),
        ],
        rows=[
            ["Apple", "Red"],
            ["Banana", "Yellow"],
            ["Cherry", "Purple"],
        ],
    )

    page = user_source_user_fixture["page"]
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=user_source_user_fixture["integration"],
        table=table,
        row_id="2",
    )

    builder = page.builder
    builder.workspace = None
    builder.save()
    data_fixture.create_builder_custom_domain(published_to=builder)

    url = reverse(
        "api:builder:domains:public_dispatch_all",
        kwargs={"page_id": page.id},
    )
    user_token = user_source_user_fixture["user_source_user_token"]

    response = api_client.post(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {user_token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {str(data_source.id): {}}


@pytest.mark.django_db
def test_public_dispatch_data_sources_list_rows_no_elements(
    api_client, data_fixture, user_source_user_fixture
):
    """
    Test the DispatchDataSourcesView endpoint when using a Data Source type
    of List Rows.

    If the page has zero elements, the API response should not contain any
    field specific data.
    """

    user = user_source_user_fixture["user"]
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("Color", "text"),
        ],
        rows=[
            ["Apple", "Red"],
            ["Banana", "Yellow"],
            ["Cherry", "Purple"],
        ],
    )

    page = user_source_user_fixture["page"]
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=user,
        page=page,
        integration=user_source_user_fixture["integration"],
        table=table,
    )

    builder = user_source_user_fixture["builder"]
    builder.workspace = None
    builder.save()
    data_fixture.create_builder_custom_domain(published_to=builder)

    url = reverse(
        "api:builder:domains:public_dispatch_all",
        kwargs={"page_id": page.id},
    )
    user_token = user_source_user_fixture["user_source_user_token"]

    response = api_client.post(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {user_token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        str(data_source.id): {"has_next_page": False, "results": []}
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "user_role,element_role,expect_fields",
    [
        # When the user role doesn't match the Element's role,
        # the fields should *not* be returned.
        ("foo_role", "bar_role", False),
        # When the user and Element roles match, the fields should
        # be returned.
        ("foo_role", "foo_role", True),
    ],
)
def test_public_dispatch_data_sources_list_rows_with_elements_and_role(
    api_client,
    data_fixture,
    data_source_element_roles_fixture,
    user_role,
    element_role,
    expect_fields,
):
    """
    Test the DispatchDataSourcesView endpoint when using a Data Source type
    of List Rows.

    This test creates a Element with a role. Depending on whether expect_fields
    is True or False, the test checks to see if the Data Source view returns
    the fields.

    The API response should only contain field data when the field is
    referenced in an element via a formula, and that element is visible
    to the user.
    """

    page = data_source_element_roles_fixture["page"]

    user_source, integration = data_fixture.create_user_table_and_role(
        data_source_element_roles_fixture["user"],
        data_source_element_roles_fixture["builder_to"],
        user_role,
    )
    user_source_user = UserSourceUser(
        user_source, None, 1, "foo_username", "foo@bar.com"
    )
    token = user_source_user.get_refresh_token().access_token

    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=data_source_element_roles_fixture["user"],
        page=page,
        integration=integration,
        table=data_source_element_roles_fixture["table"],
    )

    field = data_source_element_roles_fixture["fields"][0]
    field_id = field.id

    # Create an element that uses a formula referencing the data source
    data_fixture.create_builder_table_element(
        page=page,
        data_source=data_source,
        visibility=Element.VISIBILITY_TYPES.LOGGED_IN,
        roles=[element_role],
        role_type=Element.ROLE_TYPES.DISALLOW_ALL_EXCEPT,
        fields=[
            {
                "name": "FieldA",
                "type": "text",
                "config": {"value": f"get('current_record.field_{field_id}')"},
            },
        ],
    )

    url = reverse(
        "api:builder:domains:public_dispatch_all",
        kwargs={"page_id": page.id},
    )

    response = api_client.post(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    expected_results = []
    for row in data_source_element_roles_fixture["rows"]:
        result = {"id": row.id}
        if expect_fields:
            # Field should only be visible if the user's role allows them
            # to see the data source fields.
            result[field.name] = getattr(row, f"field_{field_id}")

        expected_results.append(result)

    assert response.status_code == HTTP_200_OK

    if expect_fields:
        assert response.json() == {
            str(data_source.id): {
                "has_next_page": False,
                "results": expected_results,
            },
        }
    else:
        assert response.json() == {
            str(data_source.id): {
                "has_next_page": False,
                "results": [],
            },
        }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "user_role,page_role_type,page_roles,element_role,expect_fields",
    [
        (
            "foo_role",
            Page.ROLE_TYPES.ALLOW_ALL,
            [],
            "",
            True,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.ALLOW_ALL_EXCEPT,
            [],
            "",
            True,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.ALLOW_ALL_EXCEPT,
            ["foo_role"],
            "",
            False,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.DISALLOW_ALL_EXCEPT,
            [],
            "",
            False,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.DISALLOW_ALL_EXCEPT,
            ["foo_role"],
            "",
            True,
        ),
        # The following should all fail (no field info returned) because
        # although the Page visiblity allows access, the Element visibility
        # does not.
        (
            "foo_role",
            Page.ROLE_TYPES.ALLOW_ALL,
            [],
            "foo_role",
            False,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.ALLOW_ALL_EXCEPT,
            [],
            "foo_role",
            False,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.ALLOW_ALL_EXCEPT,
            ["foo_role"],
            "foo_role",
            False,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.DISALLOW_ALL_EXCEPT,
            [],
            "foo_role",
            False,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.DISALLOW_ALL_EXCEPT,
            ["foo_role"],
            "foo_role",
            False,
        ),
    ],
)
def test_public_dispatch_data_sources_list_rows_with_page_visibility_all(
    api_client,
    data_fixture,
    data_source_element_roles_fixture,
    user_role,
    page_role_type,
    page_roles,
    element_role,
    expect_fields,
):
    """
    Test the DispatchDataSourcesView endpoint when using a Data Source type
    of List Rows.

    This test checks that the page's visibility setting is correctly evaluated
    when filtering the elements for the API response. The response should only
    contain field data if the page's visibility settings allow it.

    When the visibility_type is 'all', the API should return fields regardless
    of the role_type or roles list. However, it should still respect the element
    level visibility.
    """

    page = data_source_element_roles_fixture["page"]
    page.visibility = Page.VISIBILITY_TYPES.ALL
    page.role_type = page_role_type
    page.roles = page_roles
    page.save()

    user_source, integration = data_fixture.create_user_table_and_role(
        data_source_element_roles_fixture["user"],
        data_source_element_roles_fixture["builder_to"],
        user_role,
    )
    user_source_user = UserSourceUser(
        user_source, None, 1, "foo_username", "foo@bar.com"
    )
    token = user_source_user.get_refresh_token().access_token

    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=data_source_element_roles_fixture["user"],
        page=page,
        integration=integration,
        table=data_source_element_roles_fixture["table"],
    )

    field_id = data_source_element_roles_fixture["fields"][0].id

    # Create an element that uses a formula referencing the data source
    data_fixture.create_builder_table_element(
        page=page,
        data_source=data_source,
        visibility=Element.VISIBILITY_TYPES.LOGGED_IN,
        roles=[element_role],
        role_type=Element.ROLE_TYPES.ALLOW_ALL_EXCEPT,
        fields=[
            {
                "name": "FieldA",
                "type": "text",
                "config": {"value": f"get('current_record.field_{field_id}')"},
            },
        ],
    )

    url = reverse(
        "api:builder:domains:public_dispatch_all",
        kwargs={"page_id": page.id},
    )

    response = api_client.post(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK

    rows = data_source_element_roles_fixture["rows"]

    if expect_fields:
        field_name = data_source_element_roles_fixture["fields"][0].name
        assert response.json() == {
            str(data_source.id): {
                "has_next_page": False,
                "results": [
                    {field_name: "Apple", "id": rows[0].id},
                    {field_name: "Banana", "id": rows[1].id},
                    {field_name: "Cherry", "id": rows[2].id},
                ],
            },
        }
    else:
        assert response.json() == {
            str(data_source.id): {
                "has_next_page": False,
                "results": [],
            },
        }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "user_role,page_role_type,page_roles,element_role,expect_fields",
    [
        (
            "foo_role",
            Page.ROLE_TYPES.ALLOW_ALL,
            [],
            "",
            True,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.ALLOW_ALL_EXCEPT,
            [],
            "",
            True,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.ALLOW_ALL_EXCEPT,
            ["foo_role"],
            "",
            False,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.DISALLOW_ALL_EXCEPT,
            [],
            "",
            False,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.DISALLOW_ALL_EXCEPT,
            ["foo_role"],
            "",
            True,
        ),
        # The following should all fail (no field info returned) because
        # although the Page visiblity allows access, the Element visibility
        # does not.
        (
            "foo_role",
            Page.ROLE_TYPES.ALLOW_ALL,
            [],
            "foo_role",
            False,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.ALLOW_ALL_EXCEPT,
            [],
            "foo_role",
            False,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.ALLOW_ALL_EXCEPT,
            ["foo_role"],
            "foo_role",
            False,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.DISALLOW_ALL_EXCEPT,
            [],
            "foo_role",
            False,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.DISALLOW_ALL_EXCEPT,
            ["foo_role"],
            "foo_role",
            False,
        ),
    ],
)
def test_public_dispatch_data_sources_get_row_with_page_visibility_all(
    api_client,
    data_fixture,
    data_source_element_roles_fixture,
    user_role,
    page_role_type,
    page_roles,
    element_role,
    expect_fields,
):
    """
    Test the DispatchDataSourcesView endpoint when using a Data Source type
    of Get Row.

    This test checks that the page's visibility setting is correctly evaluated
    when filtering the elements for the API response. The response should only
    contain field data if the page's visibility settings allow it.

    When the visibility_type is 'all', the API should return fields regardless
    of the role_type or roles list. However, it should still respect the element
    level visibility.
    """

    page = data_source_element_roles_fixture["page"]
    page.visibility = Page.VISIBILITY_TYPES.ALL
    page.role_type = page_role_type
    page.roles = page_roles
    page.save()

    user_source, integration = data_fixture.create_user_table_and_role(
        data_source_element_roles_fixture["user"],
        data_source_element_roles_fixture["builder_to"],
        user_role,
    )
    user_source_user = UserSourceUser(
        user_source, None, 1, "foo_username", "foo@bar.com", role=user_role
    )
    token = user_source_user.get_refresh_token().access_token

    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=data_source_element_roles_fixture["user"],
        page=page,
        integration=integration,
        table=data_source_element_roles_fixture["table"],
        row_id="1",
    )

    # Create an element that uses a formula referencing the data source
    field = data_source_element_roles_fixture["fields"][0]
    field_id = field.id
    data_fixture.create_builder_heading_element(
        page=page,
        value=f"get('data_source.{data_source.id}.field_{field_id}')",
        visibility=Element.VISIBILITY_TYPES.LOGGED_IN,
        roles=[element_role],
        role_type=Element.ROLE_TYPES.ALLOW_ALL_EXCEPT,
    )

    url = reverse(
        "api:builder:domains:public_dispatch_all",
        kwargs={"page_id": page.id},
    )

    response = api_client.post(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK

    if expect_fields:
        assert response.json() == {
            str(data_source.id): {field.name: "Apple"},
        }
    else:
        assert response.json() == {str(data_source.id): {}}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "user_role,page_role_type,page_roles,element_role,expect_fields",
    [
        (
            "foo_role",
            Page.ROLE_TYPES.ALLOW_ALL,
            [],
            "foo_role",
            True,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.ALLOW_ALL_EXCEPT,
            [],
            "foo_role",
            True,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.DISALLOW_ALL_EXCEPT,
            ["foo_role"],
            "foo_role",
            True,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.ALLOW_ALL_EXCEPT,
            [],
            "bar_role",
            False,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.DISALLOW_ALL_EXCEPT,
            ["foo_role"],
            "bar_role",
            False,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.ALLOW_ALL_EXCEPT,
            ["foo_role"],
            "foo_role",
            False,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.DISALLOW_ALL_EXCEPT,
            [],
            "foo_role",
            False,
        ),
    ],
)
def test_public_dispatch_data_sources_list_rows_with_page_visibility_logged_in(
    api_client,
    data_fixture,
    data_source_element_roles_fixture,
    user_role,
    page_role_type,
    page_roles,
    element_role,
    expect_fields,
):
    """
    Test the DispatchDataSourcesView endpoint when using a Data Source type
    of List Rows.

    This test checks that the page's visibility setting is correctly evaluated
    when filtering the elements for the API response. The response should only
    contain field data if the page's visibility settings allow it.

    When the visibility_type is 'logged-in', the API should return fields only
    when the user is logged in and has an allowed roles. It should also still
    respect the element level visibility.
    """

    page = data_source_element_roles_fixture["page"]
    page.visibility = Page.VISIBILITY_TYPES.LOGGED_IN
    page.role_type = page_role_type
    page.roles = page_roles
    page.save()

    user_source, integration = data_fixture.create_user_table_and_role(
        data_source_element_roles_fixture["user"],
        data_source_element_roles_fixture["builder_to"],
        user_role,
    )
    user_source_user = UserSourceUser(
        user_source, None, 1, "foo_username", "foo@bar.com"
    )
    token = user_source_user.get_refresh_token().access_token

    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=data_source_element_roles_fixture["user"],
        page=page,
        integration=integration,
        table=data_source_element_roles_fixture["table"],
    )

    field_id = data_source_element_roles_fixture["fields"][0].id

    # Create an element that uses a formula referencing the data source
    data_fixture.create_builder_table_element(
        page=page,
        data_source=data_source,
        visibility=Element.VISIBILITY_TYPES.LOGGED_IN,
        roles=[element_role],
        role_type=Element.ROLE_TYPES.DISALLOW_ALL_EXCEPT,
        fields=[
            {
                "name": "FieldA",
                "type": "text",
                "config": {"value": f"get('current_record.field_{field_id}')"},
            },
        ],
    )

    url = reverse(
        "api:builder:domains:public_dispatch_all",
        kwargs={"page_id": page.id},
    )

    response = api_client.post(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK

    rows = data_source_element_roles_fixture["rows"]

    if expect_fields:
        field_name = data_source_element_roles_fixture["fields"][0].name
        assert response.json() == {
            str(data_source.id): {
                "has_next_page": False,
                "results": [
                    {field_name: "Apple", "id": rows[0].id},
                    {field_name: "Banana", "id": rows[1].id},
                    {field_name: "Cherry", "id": rows[2].id},
                ],
            },
        }
    else:
        assert response.json() == {
            str(data_source.id): {
                "has_next_page": False,
                "results": [],
            },
        }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "user_role,page_role_type,page_roles,element_role,expect_fields",
    [
        (
            "foo_role",
            Page.ROLE_TYPES.ALLOW_ALL,
            [],
            "foo_role",
            True,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.ALLOW_ALL_EXCEPT,
            [],
            "foo_role",
            True,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.DISALLOW_ALL_EXCEPT,
            ["foo_role"],
            "foo_role",
            True,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.ALLOW_ALL_EXCEPT,
            [],
            "bar_role",
            False,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.DISALLOW_ALL_EXCEPT,
            ["foo_role"],
            "bar_role",
            False,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.ALLOW_ALL_EXCEPT,
            ["foo_role"],
            "foo_role",
            False,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.DISALLOW_ALL_EXCEPT,
            [],
            "foo_role",
            False,
        ),
    ],
)
def test_public_dispatch_data_sources_get_row_with_page_visibility_logged_in(
    api_client,
    data_fixture,
    data_source_element_roles_fixture,
    user_role,
    page_role_type,
    page_roles,
    element_role,
    expect_fields,
):
    """
    Test the DispatchDataSourcesView endpoint when using a Data Source type
    of Get Row.

    This test checks that the page's visibility setting is correctly evaluated
    when filtering the elements for the API response. The response should only
    contain field data if the page's visibility settings allow it.

    When the visibility_type is 'logged-in', the API should return fields only
    when the user is logged in and has an allowed roles. It should also still
    respect the element level visibility.
    """

    page = data_source_element_roles_fixture["page"]
    page.visibility = Page.VISIBILITY_TYPES.LOGGED_IN
    page.role_type = page_role_type
    page.roles = page_roles
    page.save()

    user_source, integration = data_fixture.create_user_table_and_role(
        data_source_element_roles_fixture["user"],
        data_source_element_roles_fixture["builder_to"],
        user_role,
    )
    user_source_user = UserSourceUser(
        user_source, None, 1, "foo_username", "foo@bar.com", role=user_role
    )
    token = user_source_user.get_refresh_token().access_token

    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=data_source_element_roles_fixture["user"],
        page=page,
        integration=integration,
        table=data_source_element_roles_fixture["table"],
        row_id="1",
    )

    # Create an element that uses a formula referencing the data source
    field_id = data_source_element_roles_fixture["fields"][0].id
    data_fixture.create_builder_heading_element(
        page=page,
        value=f"get('data_source.{data_source.id}.field_{field_id}')",
        visibility=Element.VISIBILITY_TYPES.LOGGED_IN,
        roles=[element_role],
        role_type=Element.ROLE_TYPES.DISALLOW_ALL_EXCEPT,
    )

    url = reverse(
        "api:builder:domains:public_dispatch_all",
        kwargs={"page_id": page.id},
    )

    response = api_client.post(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK

    if expect_fields:
        assert response.json() == {
            str(data_source.id): {
                data_source_element_roles_fixture["fields"][0].name: "Apple"
            },
        }
    else:
        assert response.json() == {str(data_source.id): {}}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "user_role,page_role_type,page_roles,element_role,expect_fields",
    [
        (
            "foo_role",
            Page.ROLE_TYPES.ALLOW_ALL,
            [],
            "foo_role",
            True,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.ALLOW_ALL,
            [],
            "",
            False,
        ),
    ],
)
def test_list_elements_with_page_visibility_all(
    api_client,
    data_fixture,
    data_source_element_roles_fixture,
    user_role,
    page_role_type,
    page_roles,
    element_role,
    expect_fields,
):
    """
    Test the PublicElementsView endpoint.

    When the Page visibility is set to 'all', all elements should be returned
    regardless of the user's role or logged in status.

    However, Element visibility settings should still be applied.
    """

    page = data_source_element_roles_fixture["page"]
    page.visibility = Page.VISIBILITY_TYPES.ALL
    page.role_type = page_role_type
    page.roles = page_roles
    page.save()

    user_source, integration = data_fixture.create_user_table_and_role(
        data_source_element_roles_fixture["user"],
        data_source_element_roles_fixture["builder_to"],
        user_role,
    )
    user_source_user = UserSourceUser(
        user_source, None, 1, "foo_username", "foo@bar.com", role=user_role
    )
    token = user_source_user.get_refresh_token().access_token

    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=data_source_element_roles_fixture["user"],
        page=page,
        integration=integration,
        table=data_source_element_roles_fixture["table"],
        row_id="1",
    )

    # Create an element that uses a formula referencing the data source
    field_id = data_source_element_roles_fixture["fields"][0].id

    element = data_fixture.create_builder_heading_element(
        page=page,
        value=f"get('data_source.{data_source.id}.field_{field_id}')",
        visibility=Element.VISIBILITY_TYPES.LOGGED_IN,
        roles=[element_role],
        role_type=Element.ROLE_TYPES.DISALLOW_ALL_EXCEPT,
    )

    url = reverse(
        "api:builder:domains:list_elements",
        kwargs={"page_id": page.id},
    )

    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK

    if expect_fields:
        assert [e["id"] for e in response.json()] == [element.id]
    else:
        assert response.json() == []


@pytest.mark.django_db
@pytest.mark.parametrize(
    "user_role,page_role_type,page_roles,element_role,expect_fields",
    [
        (
            "foo_role",
            Page.ROLE_TYPES.ALLOW_ALL,
            [],
            "foo_role",
            True,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.ALLOW_ALL,
            [],
            "bar_role",
            False,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.ALLOW_ALL_EXCEPT,
            [],
            "foo_role",
            True,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.ALLOW_ALL_EXCEPT,
            [],
            "bar_role",
            False,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.ALLOW_ALL_EXCEPT,
            ["foo_role"],
            "foo_role",
            False,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.DISALLOW_ALL_EXCEPT,
            ["foo_role"],
            "foo_role",
            True,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.DISALLOW_ALL_EXCEPT,
            ["foo_role"],
            "bar_role",
            False,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.DISALLOW_ALL_EXCEPT,
            ["bar_role"],
            "foo_role",
            False,
        ),
    ],
)
def test_list_elements_with_page_visibility_logged_in(
    api_client,
    data_fixture,
    data_source_element_roles_fixture,
    user_role,
    page_role_type,
    page_roles,
    element_role,
    expect_fields,
):
    """
    Test the PublicElementsView endpoint.

    When the Page visibility is 'logged-in', ensure that the user is authenticated
    and that the user's role is allowed access based on the Element's visibility
    settings.
    """

    page = data_source_element_roles_fixture["page"]
    page.visibility = Page.VISIBILITY_TYPES.LOGGED_IN
    page.role_type = page_role_type
    page.roles = page_roles
    page.save()

    user_source, integration = data_fixture.create_user_table_and_role(
        data_source_element_roles_fixture["user"],
        data_source_element_roles_fixture["builder_to"],
        user_role,
    )
    user_source_user = UserSourceUser(
        user_source, None, 1, "foo_username", "foo@bar.com", role=user_role
    )
    token = user_source_user.get_refresh_token().access_token

    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=data_source_element_roles_fixture["user"],
        page=page,
        integration=integration,
        table=data_source_element_roles_fixture["table"],
        row_id="1",
    )

    # Create an element that uses a formula referencing the data source
    field_id = data_source_element_roles_fixture["fields"][0].id

    element = data_fixture.create_builder_heading_element(
        page=page,
        value=f"get('data_source.{data_source.id}.field_{field_id}')",
        visibility=Element.VISIBILITY_TYPES.LOGGED_IN,
        roles=[element_role],
        role_type=Element.ROLE_TYPES.DISALLOW_ALL_EXCEPT,
    )

    url = reverse(
        "api:builder:domains:list_elements",
        kwargs={"page_id": page.id},
    )

    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK

    if expect_fields:
        assert [e["id"] for e in response.json()] == [element.id]

    else:
        assert response.json() == []


@pytest.mark.django_db
def test_get_data_source_context_fields_are_excluded(api_client, data_fixture):
    """
    Test the PublicDataSourcesView. Ensure that data source context fields are
    filtered out from the response.
    """

    user = data_fixture.create_user()
    builder_from = data_fixture.create_builder_application(user=user)
    builder_to = data_fixture.create_builder_application(user=user, workspace=None)
    page = data_fixture.create_builder_page(builder=builder_to, user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=builder_to, authorized_user=user, name="test"
    )
    database = data_fixture.create_database_application(workspace=builder_to.workspace)
    table = data_fixture.create_database_table(database=database)
    multiple_select_field = data_fixture.create_multiple_select_field(
        table=table, name="option_field", order=1, primary=True
    )
    option_1 = data_fixture.create_select_option(
        field=multiple_select_field, value="doom-red", color="red", order=0
    )
    option_2 = data_fixture.create_select_option(
        field=multiple_select_field, value="quake-green", color="green", order=1
    )
    option_3 = data_fixture.create_select_option(
        field=multiple_select_field, value="warcraft-blue", color="blue", order=1
    )
    options = [option_1, option_2, option_3]

    data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page, user=user, integration=integration, table=table, row_id="1"
    )
    data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page, user=user, integration=integration, table=table
    )

    data_fixture.create_builder_custom_domain(
        domain_name="test.getbaserow.io",
        published_to=page.builder,
        builder=builder_from,
    )

    url = reverse(
        "api:builder:domains:list_data_sources",
        kwargs={"page_id": page.id},
    )
    response = api_client.get(
        url,
        format="json",
    )

    response_json = response.json()

    assert response.status_code == HTTP_200_OK

    # Test the Get Row data source
    field_name = f"field_{multiple_select_field.id}"
    assert response_json[0]["context_data"] == {}
    assert field_name not in response_json[0]["schema"]["properties"]
    assert field_name not in response_json[0]["schema"]["properties"]

    # Test the List Rows data source
    assert response_json[1]["context_data"] == {}
    assert field_name not in response_json[1]["schema"]["items"]["properties"]


@pytest.mark.django_db
def test_get_data_source_context_fields_are_included(api_client, data_fixture):
    """
    Test the PublicDataSourcesView. Ensure that data source context fields are
    included if they are used by an element.
    """

    user = data_fixture.create_user()
    builder_from = data_fixture.create_builder_application(user=user)
    builder_to = data_fixture.create_builder_application(user=user, workspace=None)
    page = data_fixture.create_builder_page(builder=builder_to, user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=builder_to, authorized_user=user, name="test"
    )
    database = data_fixture.create_database_application(workspace=builder_to.workspace)
    table = data_fixture.create_database_table(database=database)
    multiple_select_field = data_fixture.create_multiple_select_field(
        table=table, name="option_field", order=1, primary=True
    )
    option_1 = data_fixture.create_select_option(
        field=multiple_select_field, value="doom-red", color="red", order=0
    )
    option_2 = data_fixture.create_select_option(
        field=multiple_select_field, value="quake-green", color="green", order=1
    )
    option_3 = data_fixture.create_select_option(
        field=multiple_select_field, value="warcraft-blue", color="blue", order=1
    )
    options = [option_1, option_2, option_3]

    data_source_1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page, user=user, integration=integration, table=table, row_id="1"
    )
    data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page, user=user, integration=integration, table=table
    )

    # Create an element that uses the field
    data_fixture.create_builder_heading_element(
        page=page,
        value=f"get('data_source.{data_source_1.id}.field_{multiple_select_field.id}')",
    )

    data_fixture.create_builder_custom_domain(
        domain_name="test.getbaserow.io",
        published_to=page.builder,
        builder=builder_from,
    )

    url = reverse(
        "api:builder:domains:list_data_sources",
        kwargs={"page_id": page.id},
    )
    response = api_client.get(
        url,
        format="json",
    )

    response_json = response.json()

    assert response.status_code == HTTP_200_OK

    expected_context_data = [
        {
            "color": option.color,
            "id": option.id,
            "value": option.value,
        }
        for option in options
    ]
    expected_properties = {
        "color": {
            "title": "color",
            "type": "string",
        },
        "id": {
            "title": "id",
            "type": "number",
        },
        "value": {
            "title": "value",
            "type": "string",
        },
    }

    # Test the Get Row data source
    field_name = f"field_{multiple_select_field.id}"
    assert response_json[0]["context_data"] == {field_name: expected_context_data}
    assert (
        response_json[0]["schema"]["properties"][field_name]["items"]["properties"]
        == expected_properties
    )
    assert (
        response_json[0]["schema"]["properties"][field_name]["metadata"][
            "select_options"
        ]
        == expected_context_data
    )

    # Test the List Rows data source
    assert response_json[1]["context_data"] == {field_name: expected_context_data}
    assert (
        response_json[1]["schema"]["items"]["properties"][field_name]["items"][
            "properties"
        ]
        == expected_properties
    )
    assert (
        response_json[1]["schema"]["items"]["properties"][field_name]["metadata"][
            "select_options"
        ]
        == expected_context_data
    )


@pytest.mark.django_db
def test_public_dispatch_data_source_with_refinements_referencing_trashed_field(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table, fields, rows = data_fixture.build_table(
        user=user,
        database=database,
        columns=[
            ("Name", "text"),
            ("Color", "text"),
        ],
        rows=[
            ["Apple", "Red"],
            ["Banana", "Yellow"],
            ["Cherry", "Purple"],
        ],
    )
    trashed_field = data_fixture.create_text_field(table=table, trashed=True)
    builder = data_fixture.create_builder_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=user,
        page=page,
        integration=integration,
        table=table,
    )
    service_filter = data_fixture.create_local_baserow_table_service_filter(
        service=data_source.service, field=trashed_field, value="abc", order=0
    )

    data_fixture.create_builder_heading_element(
        page=page,
        value=f"get('data_source.{data_source.id}.field_{fields[0].id}')",
    )

    url = reverse(
        "api:builder:domains:public_dispatch",
        kwargs={"data_source_id": data_source.id},
    )
    response = api_client.post(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_SERVICE_FILTER_PROPERTY_DOES_NOT_EXIST",
        "detail": "A data source filter is misconfigured: "
        "One or more filtered properties no longer exist.",
    }

    service_filter.delete()

    data_fixture.create_local_baserow_table_service_sort(
        service=data_source.service,
        field=trashed_field,
        order_by=SORT_ORDER_ASC,
        order=0,
    )

    response = api_client.post(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_SERVICE_SORT_PROPERTY_DOES_NOT_EXIST",
        "detail": "A data source sort is misconfigured: "
        "One or more sorted properties no longer exist.",
    }
