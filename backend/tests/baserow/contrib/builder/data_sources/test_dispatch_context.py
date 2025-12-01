import json
from unittest.mock import MagicMock, Mock, patch

from django.http import HttpRequest

import pytest
from rest_framework.request import Request

from baserow.contrib.builder.data_sources.builder_dispatch_context import (
    BuilderDispatchContext,
)
from baserow.contrib.builder.data_sources.exceptions import (
    DataSourceRefinementForbidden,
)
from baserow.contrib.builder.elements.element_types import collection_element_types
from baserow.core.services.utils import ServiceAdhocRefinements
from baserow.core.user_sources.user_source_user import UserSourceUser


def test_dispatch_context_page_range():
    request = HttpRequest()
    request.GET = {"offset": 42, "count": 42}

    dispatch_context = BuilderDispatchContext(request, None)

    assert dispatch_context.range(None) == [42, 42]

    request.GET = {"offset": "foo", "count": "bar"}

    dispatch_context = BuilderDispatchContext(request, None)

    assert dispatch_context.range(None) == [0, None]

    request.GET = {"offset": "-20", "count": "-10"}

    dispatch_context = BuilderDispatchContext(request, None)

    assert dispatch_context.range(None) == [0, 0]


@pytest.mark.django_db
@patch("baserow.contrib.builder.handler.get_builder_used_property_names")
def test_dispatch_context_page_clone(mock_get_field_names, data_fixture):
    mock_get_field_names.return_value = {"all": {}, "external": {}, "internal": {}}

    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)

    user_source, integration = data_fixture.create_user_table_and_role(
        user,
        page.builder,
        "foo_user_role",
    )
    user_source_user = UserSourceUser(
        user_source, None, 1, "foo_username", "foo@bar.com", role="foo_user_role"
    )

    request = Request(HttpRequest())
    request.user_source_user = user_source_user

    dispatch_context = BuilderDispatchContext(
        request, page, offset=0, count=5, only_expose_public_allowed_properties=True
    )
    dispatch_context.annotated_data = "foobar"

    dispatch_context.cache = {"key": "value"}
    new_dispatch_context = dispatch_context.clone(offset=5, count=1)

    assert getattr(new_dispatch_context, "annotated_data", None) is None
    assert new_dispatch_context.cache == {"key": "value"}
    assert new_dispatch_context.request == request
    assert new_dispatch_context.page == page
    assert new_dispatch_context.offset == 5
    assert new_dispatch_context.count == 1
    assert new_dispatch_context.public_allowed_properties == {
        "all": {},
        "external": {},
        "internal": {},
    }


@pytest.mark.django_db
def test_dispatch_context_element_type(data_fixture):
    element = data_fixture.create_builder_repeat_element()
    element_type = element.get_type()

    dispatch_context = BuilderDispatchContext(HttpRequest(), Mock())
    assert dispatch_context.element_type is None

    fake_request = HttpRequest()
    fake_request.data = {
        "metadata": json.dumps(
            {
                "data_source": {"element": element.id},
            }
        )
    }
    dispatch_context = BuilderDispatchContext(fake_request, element.page)
    assert dispatch_context.element_type == element_type


def test_dispatch_context_search_query():
    request = HttpRequest()
    request.GET["search_query"] = "foobar"
    dispatch_context = BuilderDispatchContext(request, None)
    assert dispatch_context.search_query() == "foobar"


@pytest.mark.django_db
@pytest.mark.parametrize("collection_element_type", collection_element_types())
def test_dispatch_context_is_publicly_searchable(collection_element_type, data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    element = collection_element_type.model_class.objects.create(page=page)
    fake_request = HttpRequest()
    fake_request.data = {
        "metadata": json.dumps(
            {
                "data_source": {"element": element.id},
            }
        )
    }
    dispatch_context = BuilderDispatchContext(fake_request, page)
    assert (
        dispatch_context.is_publicly_searchable
        == collection_element_type.is_publicly_searchable
    )


@pytest.mark.django_db
def test_dispatch_context_searchable_fields(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    dispatch_context = BuilderDispatchContext(HttpRequest(), page)
    with pytest.raises(DataSourceRefinementForbidden):
        dispatch_context.searchable_fields()
    element = data_fixture.create_builder_table_element(page=page)
    element.property_options.create(schema_property="name", searchable=True)
    element.property_options.create(schema_property="location", searchable=True)
    element.property_options.create(schema_property="top_secret", searchable=False)

    fake_request = HttpRequest()
    fake_request.data = {
        "metadata": json.dumps(
            {
                "data_source": {"element": element.id},
            }
        )
    }

    dispatch_context = BuilderDispatchContext(fake_request, page)
    assert dispatch_context.searchable_fields() == ["name", "location"]


@pytest.mark.django_db
@pytest.mark.parametrize("collection_element_type", collection_element_types())
def test_dispatch_context_is_publicly_filterable(collection_element_type, data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    element = collection_element_type.model_class.objects.create(page=page)

    fake_request = HttpRequest()
    fake_request.data = {
        "metadata": json.dumps(
            {
                "data_source": {"element": element.id},
            }
        )
    }

    dispatch_context = BuilderDispatchContext(fake_request, page)
    assert (
        dispatch_context.is_publicly_filterable
        == collection_element_type.is_publicly_filterable
    )


def test_dispatch_context_filters():
    request = HttpRequest()
    filter_data = {
        "groups": [],
        "filter_type": "AND",
        "filters": [
            {
                "field": 123,
                "type": "contains",
                "value": "Alexa",
            }
        ],
    }
    request.GET["filters"] = filter_data
    dispatch_context = BuilderDispatchContext(request, None)
    assert dispatch_context.filters() == filter_data


@pytest.mark.django_db
@pytest.mark.parametrize("collection_element_type", collection_element_types())
def test_dispatch_context_is_publicly_sortable(collection_element_type, data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    element = collection_element_type.model_class.objects.create(page=page)

    fake_request = HttpRequest()
    fake_request.data = {
        "metadata": json.dumps(
            {
                "data_source": {"element": element.id},
            }
        )
    }

    dispatch_context = BuilderDispatchContext(fake_request, page)
    assert (
        dispatch_context.is_publicly_sortable
        == collection_element_type.is_publicly_sortable
    )


def test_dispatch_context_sortings():
    request = HttpRequest()
    request.GET["order_by"] = "-field_1,-field_2"
    dispatch_context = BuilderDispatchContext(request, None)
    assert dispatch_context.sortings() == "-field_1,-field_2"


@pytest.mark.parametrize(
    "only_expose_public_allowed_properties",
    (
        [True],
        [True],
        [False],
        [False],
    ),
)
@patch("baserow.contrib.builder.handler.get_builder_used_property_names")
def test_builder_dispatch_context_field_names_computed_on_param(
    mock_get_builder_used_property_names,
    only_expose_public_allowed_properties,
):
    """
    Test the BuilderDispatchContext::public_allowed_properties property.

    Ensure that the public_allowed_properties property is computed
    depending on the param.
    """

    mock_field_names = ["field_123"]
    mock_get_builder_used_property_names.return_value = mock_field_names

    mock_request = HttpRequest()
    mock_request.user_source_user = MagicMock()
    mock_request.user_source_user.is_anonymous = True
    mock_page = MagicMock()
    mock_page.builder = MagicMock()

    dispatch_context = BuilderDispatchContext(
        mock_request,
        mock_page,
        only_expose_public_allowed_properties=only_expose_public_allowed_properties,
    )

    if only_expose_public_allowed_properties:
        assert dispatch_context.public_allowed_properties == mock_field_names
        mock_get_builder_used_property_names.assert_called_once_with(
            mock_request.user_source_user, mock_page.builder
        )
    else:
        assert dispatch_context.public_allowed_properties is None
        mock_get_builder_used_property_names.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "property_option_params",
    [
        {
            "schema_property": "name",
            "filterable": True,
            "sortable": False,
            "searchable": False,
        },
        {
            "schema_property": "age",
            "filterable": False,
            "sortable": True,
            "searchable": False,
        },
        {
            "schema_property": "location",
            "filterable": False,
            "sortable": False,
            "searchable": True,
        },
    ],
)
def test_validate_filter_search_sort_fields(data_fixture, property_option_params):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_table_element(page=page)
    element.property_options.create(**property_option_params)

    fake_request = HttpRequest()
    fake_request.data = {
        "metadata": json.dumps(
            {
                "data_source": {"element": element.id},
            }
        )
    }

    dispatch_context = BuilderDispatchContext(fake_request, page)
    schema_property = property_option_params["schema_property"]
    for refinement in list(ServiceAdhocRefinements):
        model_field_name = ServiceAdhocRefinements.to_model_field(refinement)
        if property_option_params[model_field_name]:
            dispatch_context.validate_filter_search_sort_fields(
                [schema_property], refinement
            )
        else:
            with pytest.raises(DataSourceRefinementForbidden) as exc:
                dispatch_context.validate_filter_search_sort_fields(
                    [schema_property], refinement
                )
            assert (
                exc.value.args[0]
                == f"{schema_property} is not a {model_field_name} field."
            )


@pytest.mark.django_db
def test_get_element_property_options(data_fixture, django_assert_num_queries):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_table_element(page=page)
    element.property_options.create(
        schema_property="name", filterable=True, sortable=False, searchable=False
    )
    fake_request = HttpRequest()
    fake_request.data = {
        "metadata": json.dumps(
            {
                "data_source": {"element": element.id},
            }
        )
    }

    dispatch_context = BuilderDispatchContext(fake_request, page)
    assert dispatch_context.cache == {}
    with django_assert_num_queries(1):
        dispatch_context.get_element_property_options()
    assert dispatch_context.cache["element_property_options"] == {
        "name": {"filterable": True, "sortable": False, "searchable": False}
    }
    with django_assert_num_queries(0):
        dispatch_context.get_element_property_options()


def test_validate_filter_search_sort_fields_without_element():
    dispatch_context = BuilderDispatchContext(HttpRequest(), None)
    with pytest.raises(DataSourceRefinementForbidden) as exc:
        dispatch_context.validate_filter_search_sort_fields(
            ["name"], ServiceAdhocRefinements.FILTER
        )
    assert (
        exc.value.args[0]
        == "An element is required to validate filter, search and sort fields."
    )


@pytest.mark.django_db
def test_validate_filter_search_sort_fields_without_collection_element(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_heading_element(page=page)
    fake_request = HttpRequest()
    fake_request.data = {
        "metadata": json.dumps(
            {
                "data_source": {"element": element.id},
            }
        )
    }

    dispatch_context = BuilderDispatchContext(fake_request, page)
    with pytest.raises(DataSourceRefinementForbidden) as exc:
        dispatch_context.validate_filter_search_sort_fields(
            ["name"], ServiceAdhocRefinements.FILTER
        )
    assert (
        exc.value.args[0] == "A collection element is required to validate filter, "
        "search and sort fields."
    )


@pytest.mark.django_db
def test_builder_dispatch_context_public_allowed_properties_is_cached(
    data_fixture, django_assert_num_queries
):
    """
    Test the BuilderDispatchContext::public_allowed_properties property.

    Ensure that the expensive call to get_formula_field_names() is cached.
    """

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

    user_source, integration = data_fixture.create_user_table_and_role(
        user,
        builder,
        "foo_user_role",
    )
    user_source_user = UserSourceUser(
        user_source, None, 1, "foo_username", "foo@bar.com", role="foo_user_role"
    )

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
    data_fixture.create_builder_heading_element(
        page=page,
        value=f"get('data_source.{data_source.id}.0.field_{fields[0].id}')",
    )

    request = Request(HttpRequest())
    request.user_source_user = user_source_user

    dispatch_context = BuilderDispatchContext(
        request,
        page,
        only_expose_public_allowed_properties=True,
    )

    expected_results = {
        "all": {data_source.service.id: [f"field_{fields[0].id}"]},
        "external": {data_source.service.id: [f"field_{fields[0].id}"]},
        "internal": {},
    }

    # Initially calling the property should cause a bunch of DB queries.
    with django_assert_num_queries(10):
        result = dispatch_context.public_allowed_properties
        assert result == expected_results

    # Subsequent calls to the property should *not* cause any DB queries.
    with django_assert_num_queries(0):
        result = dispatch_context.public_allowed_properties
        assert result == expected_results


@pytest.mark.django_db
def test_get_timezone_name_base(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)

    fake_request = HttpRequest()

    dispatch_context = BuilderDispatchContext(fake_request, page)
    # Should default to UTC
    assert dispatch_context.get_timezone_name() == "UTC"


@pytest.mark.django_db
def test_get_timezone_name_specific(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)

    fake_request = HttpRequest()
    fake_request.data = {
        "metadata": json.dumps(
            {
                "user": {"timezone": "Europe/Amsterdam"},
            }
        )
    }

    dispatch_context = BuilderDispatchContext(fake_request, page)
    # When provided by the frontend, should use the specific timezone
    assert dispatch_context.get_timezone_name() == "Europe/Amsterdam"
