from collections import defaultdict
from unittest.mock import MagicMock, patch

import pytest

from baserow.contrib.builder.data_sources.service import DataSourceService
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.elements.service import ElementService
from baserow.contrib.builder.pages.service import PageService
from baserow.contrib.database.api.rows.serializers import RowSerializer
from baserow.contrib.database.views.models import SORT_ORDER_ASC
from baserow.contrib.integrations.local_baserow.models import LocalBaserowGetRow
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowGetRowUserServiceType,
    LocalBaserowUpsertRowServiceType,
)
from baserow.core.exceptions import PermissionException
from baserow.core.services.exceptions import (
    DoesNotExist,
    InvalidContextContentDispatchException,
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.registries import service_type_registry
from baserow.core.utils import MirrorDict
from baserow.test_utils.helpers import AnyStr, setup_interesting_test_table
from baserow.test_utils.pytest_conftest import FakeDispatchContext, fake_import_formula


@pytest.mark.django_db
def test_create_local_baserow_get_row_service(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    view = data_fixture.create_grid_view(user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )

    service_type = LocalBaserowGetRowUserServiceType()
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "row_id": "1",
        },
        user,
    )
    service = ServiceHandler().create_service(service_type, **values)

    assert service.view.id == view.id
    assert service.table.id == view.table_id
    assert service.row_id["formula"] == "1"


@pytest.mark.django_db
def test_export_import_local_baserow_get_row_service(data_fixture):
    user = data_fixture.create_user()
    path_params = [
        {"name": "id", "type": "numeric"},
        {"name": "filter", "type": "text"},
    ]
    page = data_fixture.create_builder_page(
        path="/page/:id/:filter/", path_params=path_params
    )
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
        ],
        rows=[
            ["BMW"],
        ],
    )
    field = fields[0]
    view = data_fixture.create_grid_view(user, table=table)
    service_type = service_type_registry.get("local_baserow_get_row")
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    service = data_fixture.create_local_baserow_get_row_service(
        integration=integration,
        row_id="1",
        view=view,
        table=view.table,
        search_query="get('page_parameter.id')",
        filter_type="Or",
    )
    service_filter = data_fixture.create_local_baserow_table_service_filter(
        service=service, field=field, value="get('page_parameter.filter')", order=0
    )

    exported = service_type.export_serialized(service)

    assert exported == {
        "id": service.id,
        "row_id": service.row_id,
        "type": service_type.type,
        "view_id": service.view_id,
        "table_id": service.table_id,
        "integration_id": service.integration_id,
        "search_query": service.search_query,
        "filter_type": "Or",
        "sample_data": None,
        "filters": [
            {
                "field_id": service_filter.field_id,
                "type": service_filter.type,
                "value": service_filter.value,
                "value_is_formula": service_filter.value_is_formula,
            }
        ],
    }

    id_mapping = {}

    service: LocalBaserowGetRow = service_type.import_serialized(  # type: ignore
        integration, exported, id_mapping, import_formula=fake_import_formula
    )

    assert service.id != exported["id"]
    assert service.row_id == exported["row_id"]
    assert service.view_id == exported["view_id"]
    assert service.table_id == exported["table_id"]
    assert service.filter_type == exported["filter_type"]
    assert service.search_query == exported["search_query"]
    assert service.integration_id == exported["integration_id"]
    assert isinstance(service, service_type.model_class)

    assert service.service_filters.count() == 1
    service_filter = service.service_filters.get()
    assert service_filter.type == exported["filters"][0]["type"]
    assert service_filter.value == exported["filters"][0]["value"]
    assert service_filter.field_id == exported["filters"][0]["field_id"]
    assert service_filter.value_is_formula == exported["filters"][0]["value_is_formula"]

    view_2 = data_fixture.create_grid_view(user, table=table)
    field_2 = data_fixture.create_text_field(order=1, table=table)
    table_2, _, _ = data_fixture.build_table(
        columns=[("Number", "number")], rows=[[1]], user=user
    )

    id_mapping = defaultdict(lambda: MirrorDict())
    id_mapping["database_views"] = {view.id: view_2.id}  # type: ignore
    id_mapping["database_fields"] = {field.id: field_2.id}  # type: ignore
    id_mapping["database_tables"] = {table.id: table_2.id}  # type: ignore
    service: LocalBaserowGetRow = service_type.import_serialized(  # type: ignore
        integration, exported, id_mapping, import_formula=fake_import_formula
    )

    assert service.view_id == view_2.id
    assert service.table_id == table_2.id

    service_filter = service.service_filters.get()
    assert service_filter.field_id == field_2.id


@pytest.mark.django_db
def test_update_local_baserow_get_row_service(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    table = data_fixture.create_database_table(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    service = data_fixture.create_local_baserow_get_row_service(
        integration=integration, table=table, search_query="'horses'"
    )

    service_type = LocalBaserowGetRowUserServiceType()
    values = service_type.prepare_values(
        {"table_id": None, "integration_id": None, "search_query": ""}, user
    )

    ServiceHandler().update_service(service_type, service, **values)

    service.refresh_from_db()

    assert service.specific.table is None
    assert service.specific.search_query["formula"] == ""
    assert service.specific.integration is None


@pytest.mark.django_db
def test_local_baserow_get_row_service_dispatch_transform(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("My Color", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
            ["Audi", "Orange"],
        ],
    )
    view = data_fixture.create_grid_view(user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )

    service = data_fixture.create_local_baserow_get_row_service(
        integration=integration, view=view, table=table, row_id=f"{rows[1].id}"
    )

    service_type = LocalBaserowGetRowUserServiceType()

    dispatch_context = FakeDispatchContext()

    dispatch_values = LocalBaserowUpsertRowServiceType().resolve_service_formulas(
        service, dispatch_context
    )
    dispatch_data = service_type.dispatch_data(
        service, dispatch_values, dispatch_context
    )
    result = service_type.dispatch_transform(dispatch_data)

    assert result.data == {
        "id": rows[1].id,
        fields[0].name: "Audi",
        fields[1].name: "Orange",
        "order": AnyStr(),
    }


@pytest.mark.django_db
def test_local_baserow_get_row_service_dispatch_data_with_view_filter(data_fixture):
    # Demonstrates that you can fetch a specific row (1) and filter for a specific
    # value to exclude it from the `dispatch_data` result.
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
        ],
        rows=[
            ["BMW"],
            ["Audi"],
        ],
    )
    view = data_fixture.create_grid_view(user, table=table)
    data_fixture.create_view_filter(
        view=view, field=fields[0], type="contains", value="Au"
    )
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )

    service = data_fixture.create_local_baserow_get_row_service(
        integration=integration, view=view, table=table, row_id="1"
    )
    service_type = service.get_type()

    dispatch_context = FakeDispatchContext()

    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    with pytest.raises(DoesNotExist):
        service_type.dispatch_data(service, dispatch_values, dispatch_context)


@pytest.mark.django_db
def test_local_baserow_get_row_service_dispatch_data_with_service_search(
    data_fixture, disable_full_text_search
):
    # Demonstrates that you can fetch a specific row (1) and search for a specific
    # value to exclude it from the `dispatch_data` result.
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
        ],
        rows=[
            ["BMW"],
            ["Audi"],
        ],
    )
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )

    service = data_fixture.create_local_baserow_get_row_service(
        integration=integration, table=table, row_id="1", search_query="'Au'"
    )
    service_type = service.get_type()

    dispatch_context = FakeDispatchContext()

    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    with pytest.raises(DoesNotExist):
        service_type.dispatch_data(service, dispatch_values, dispatch_context)


@pytest.mark.django_db
def test_local_baserow_get_row_service_dispatch_data_with_service_integer_search(
    data_fixture, disable_full_text_search
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
        ],
        rows=[
            ["BMW"],
            ["Audi"],
            ["42"],
        ],
    )

    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )

    service = data_fixture.create_local_baserow_get_row_service(
        integration=integration, table=table, row_id="", search_query="42"
    )

    service_type = service.get_type()
    dispatch_context = FakeDispatchContext()
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)

    dispatch_data = service_type.dispatch_data(
        service, dispatch_values, dispatch_context
    )
    result = service_type.dispatch_transform(dispatch_data)

    assert result.data == {
        "id": rows[2].id,
        fields[0].name: "42",
        "order": AnyStr(),
    }


@pytest.mark.django_db
def test_local_baserow_get_row_service_dispatch_data_permission_denied(
    data_fixture, stub_check_permissions
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("My Color", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
            ["Audi", "Orange"],
        ],
    )
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )

    service = data_fixture.create_local_baserow_get_row_service(
        integration=integration, table=table, row_id="'2'"
    )

    dispatch_context = FakeDispatchContext()
    with stub_check_permissions(raise_permission_denied=True), pytest.raises(
        PermissionException
    ):
        LocalBaserowGetRowUserServiceType().dispatch_data(
            service, {"table": table}, dispatch_context
        )


@pytest.mark.django_db
def test_local_baserow_get_row_service_dispatch_validation_error(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    table = data_fixture.create_database_table(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )

    dispatch_context = FakeDispatchContext()

    service = data_fixture.create_local_baserow_get_row_service(
        integration=integration, table=None, row_id="1"
    )
    service_type = LocalBaserowGetRowUserServiceType()

    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        service_type.dispatch(service, dispatch_context)

    service = data_fixture.create_local_baserow_get_row_service(
        integration=integration, table=table, row_id="''"
    )

    with pytest.raises(InvalidContextContentDispatchException):
        service_type.dispatch(service, dispatch_context)

    service = data_fixture.create_local_baserow_get_row_service(
        integration=integration, table=table, row_id="wrong formula"
    )

    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        service_type.dispatch(service, dispatch_context)


@pytest.mark.django_db
def test_local_baserow_get_row_service_dispatch_data_row_not_exist(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    table = data_fixture.create_database_table(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )

    service = data_fixture.create_local_baserow_get_row_service(
        integration=integration, table=table, row_id="'999'"
    )
    service_type = service.get_type()

    dispatch_context = FakeDispatchContext()
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    with pytest.raises(DoesNotExist):
        service_type.dispatch_data(service, dispatch_values, dispatch_context)


@pytest.mark.django_db
def test_local_baserow_get_row_service_dispatch_data_no_row_id(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("Email", "text"),
        ],
        rows=[
            ["Ada Lovelace", "ada@baserow.io"],
            ["Blaise Pascal", "blaise@baserow.io"],
        ],
    )
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )

    service = data_fixture.create_local_baserow_get_row_service(
        integration=integration, table=table, row_id=""
    )
    service_type = service.get_type()

    dispatch_context = FakeDispatchContext()
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    dispatch_data = service_type.dispatch_data(
        service, dispatch_values, dispatch_context
    )

    assert dispatch_data["data"].id == rows[0].id

    # If the `row_id` is a formula, and its resolved value is blank or invalid,
    # ensure we're raising `InvalidContextContentDispatchException`.
    # We don't want to use the "no row ID" behaviour of returning the first row if
    # we're using formulas.
    service.row_id = 'get("page_parameter.id")'
    service.save()
    dispatch_context = FakeDispatchContext(context={"page_parameter": {"id": ""}})
    with pytest.raises(InvalidContextContentDispatchException) as exc:
        service_type.resolve_service_formulas(service, dispatch_context)

    assert exc.value.args[0] == 'Value error for "row_id": The value is required'

    dispatch_context = FakeDispatchContext(context={"page_parameter": {"id": "p"}})
    with pytest.raises(InvalidContextContentDispatchException) as exc:
        service_type.resolve_service_formulas(service, dispatch_context)

    assert (
        exc.value.args[0] == 'Value error for "row_id": '
        "The value must be an integer or convertible to an integer."
    )


@pytest.mark.django_db
def test_import_datasource_provider_formula_using_get_row_service_containing_no_field_fails_silently(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        application=builder, authorized_user=user
    )
    table = data_fixture.create_database_table(database=database)
    page = data_fixture.create_builder_page(builder=builder)
    service = data_fixture.create_local_baserow_get_row_service(
        integration=integration,
        table=table,
    )
    data_source = DataSourceService().create_data_source(
        user, service_type=service.get_type(), page=page
    )
    ElementService().create_element(
        user,
        element_type_registry.get("input_text"),
        page=page,
        data_source_id=data_source.id,
        placeholder=f"get('data_source.{data_source.id}')",
    )
    duplicated_page = PageService().duplicate_page(user, page)
    duplicated_element = duplicated_page.element_set.first()
    duplicated_data_source = duplicated_page.datasource_set.first()
    assert (
        duplicated_element.specific.placeholder["formula"]
        == f"get('data_source.{duplicated_data_source.id}')"
    )


@pytest.mark.django_db
def test_import_formula_local_baserow_get_row_user_service_type(data_fixture):
    """
    Ensure that formulas are imported correctly when importing the
    LocalBaserowGetRowUserServiceType service type.

    The LocalBaserowGetRowUserServiceType::import_path() only supports 2 path
    parts, as opposed to LocalBaserowListRowsUserServiceType::import_path()
    which supports 3.

    This means that this service type doesn't currently support Data Sources.
    Despite that, we are testing for the Data Source ID having been imported
    correctly, because this ensures that dynamic aspect of formula import is
    working.
    """

    user = data_fixture.create_user()
    path_params = [
        {"name": "id", "type": "numeric"},
        {"name": "filter", "type": "text"},
    ]
    page = data_fixture.create_builder_page(
        user=user,
        path="/page/:id/:filter/",
        path_params=path_params,
    )
    table, fields, _ = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
        ],
        rows=[
            ["BMW"],
        ],
    )
    text_field = fields[0]
    view = data_fixture.create_grid_view(user)
    service_type = service_type_registry.get("local_baserow_get_row")
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        table=table, page=page
    )
    service = data_fixture.create_local_baserow_get_row_service(
        integration=integration,
        view=view,
        table=table,
        row_id=f"get('data_source.{data_source.id}')",
        search_query=f"get('data_source.{data_source.id}')",
        filter_type="Or",
    )

    data_fixture.create_local_baserow_table_service_filter(
        service=service,
        field=text_field,
        value=f"get('data_source.{data_source.id}')",
        value_is_formula=True,
        order=0,
    )

    data_fixture.create_local_baserow_table_service_filter(
        service=service,
        field=text_field,
        value="FooServiceFilter",
        value_is_formula=False,
        order=1,
    )

    exported = service_type.export_serialized(service)

    duplicated_page = PageService().duplicate_page(user, page)
    data_source2 = duplicated_page.datasource_set.first()
    id_mapping = {"builder_data_sources": {data_source.id: data_source2.id}}

    from baserow.contrib.builder.formula_importer import import_formula

    imported_service = service_type.import_serialized(
        integration, exported, id_mapping, import_formula=import_formula
    )

    # See the docstring to understand why these formulas looks truncated.
    assert (
        imported_service.search_query["formula"]
        == f"get('data_source.{data_source2.id}')"
    )
    assert imported_service.row_id["formula"] == f"get('data_source.{data_source2.id}')"

    imported_service_filter = imported_service.service_filters.get(order=0)
    assert (
        imported_service_filter.value["formula"]
        == f"get('data_source.{data_source2.id}')"
    )

    imported_service_filter = imported_service.service_filters.get(order=1)
    assert imported_service_filter.value["formula"] == "FooServiceFilter"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path,database_fields,expected",
    [
        # The first list item is a valid field ID, but since there are no
        # database field mappings, the same path is returned.
        (
            ["field_123"],
            {},
            ["field_123"],
        ),
        # The first list item is a valid field ID, but since there are no
        # matching database field mappings, the same path is returned.
        (
            ["field_123"],
            {456: 789},
            ["field_123"],
        ),
        # The first list item is a valid field ID and matches a database field
        # mapping, as such the updated path is returned.
        (
            ["field_123"],
            {123: 456},
            ["field_456"],
        ),
        # Ensure the updated field along with the unchanged remaining parts of
        # the path are returned.
        (
            ["field_123", "foo", "bar"],
            {123: 456},
            ["field_456", "foo", "bar"],
        ),
        # If the first list item is not a valid field, ensure the path
        # is returned without any changes.
        #
        # The first list item is an integer, thus isn't a valid field.
        (
            [0, "field_123"],
            {123: 456},
            [0, "field_123"],
        ),
        # The first list item is "xfield_123", which doesn't start with
        # "field_", and thus isn't a valid field.
        (
            ["xfield_123"],
            {123: 456},
            ["xfield_123"],
        ),
    ],
)
def test_local_baserow_get_row_user_service_type_import_path(
    path, database_fields, expected
):
    """
    Ensure the LocalBaserowGetRowUserServiceType::import_path() correctly
    updates the field_id's in the path.
    """

    service_type = LocalBaserowGetRowUserServiceType()
    id_mapping = {"database_fields": database_fields}

    result = service_type.import_path(path, id_mapping)

    assert result == expected


@pytest.mark.django_db
@patch("baserow.contrib.integrations.local_baserow.service_types.CoreHandler")
@pytest.mark.parametrize(
    "view_sorts",
    (
        [],
        ["foo"],
        ["foo", "bar"],
        ["foo", "bar", "baz"],
    ),
)
def test_order_by_is_applied_depending_on_views_sorts(
    mock_core_handler, view_sorts, data_fixture
):
    """
    Test to ensure that the queryset's order_by() is only applied if
    view_sorts has items.

    If view_sorts is empty, order_by() should never be called.
    """

    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    table, _, _ = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("My Color", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
            ["Audi", "Orange"],
        ],
    )
    view = data_fixture.create_grid_view(user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )

    service = data_fixture.create_local_baserow_list_rows_service(
        integration=integration,
        view=view,
        table=table,
    )

    service_type = LocalBaserowGetRowUserServiceType()

    mock_queryset = MagicMock()

    mock_objects = MagicMock()
    mock_objects.enhance_by_fields.return_value = mock_queryset

    mock_model = MagicMock()
    mock_objects = mock_model.objects.all.return_value = mock_objects

    mock_table = MagicMock()
    mock_table.get_model.return_value = mock_model

    resolved_values = {
        "table": mock_table,
    }

    service_type.get_dispatch_search = MagicMock(return_value=None)
    service_type.get_dispatch_filters = MagicMock(return_value=mock_queryset)
    service_type.get_dispatch_sorts = MagicMock(
        return_value=(view_sorts, mock_queryset)
    )

    dispatch_context = FakeDispatchContext()
    service_type.dispatch_data(service, resolved_values, dispatch_context)

    if view_sorts:
        mock_queryset.order_by.assert_called_once_with(*view_sorts)
    else:
        mock_queryset.order_by.assert_not_called()


@pytest.mark.parametrize(
    "field_names",
    [
        None,
        {"external": {1: ["field_123"]}},
    ],
)
@patch(
    "baserow.contrib.integrations.local_baserow.service_types.get_row_serializer_class"
)
def test_dispatch_transform_passes_field_ids(mock_get_serializer, field_names):
    """
    Test the LocalBaserowGetRowUserServiceType::dispatch_transform() method.

    Ensure that the field_ids parameter is passed to the serializer class.
    """

    mock_serializer_instance = MagicMock()
    mock_serializer = MagicMock(return_value=mock_serializer_instance)
    mock_serializer.data = {}
    mock_get_serializer.return_value = mock_serializer

    service_type = LocalBaserowGetRowUserServiceType()

    dispatch_data = {
        "baserow_table_model": MagicMock(),
        "data": {},
    }
    dispatch_data["public_allowed_properties"] = field_names

    results = service_type.dispatch_transform(dispatch_data)

    assert results.data == mock_serializer.data
    mock_get_serializer.assert_called_once_with(
        dispatch_data["baserow_table_model"],
        RowSerializer,
        is_response=True,
        field_ids=None,
        user_field_names=True,
    )


@pytest.mark.parametrize(
    "path,expected",
    [
        (
            [],
            [],
        ),
        (
            ["foo"],
            [],
        ),
        (
            ["", "foo"],
            [],
        ),
        (
            ["field_123"],
            ["field_123"],
        ),
        (
            ["field_456", ""],
            ["field_456"],
        ),
        (
            ["field_789", "", ""],
            ["field_789"],
        ),
    ],
)
def test_extract_properties(path, expected):
    """
    Test the extract_properties() method.

    Given the input path, ensure the expected field name is returned.
    """

    service_type = LocalBaserowGetRowUserServiceType()

    result = service_type.extract_properties(path)

    assert result == expected


@pytest.mark.django_db
def test_can_dispatch_interesting_table(data_fixture):
    """
    Test that we can dispatch an interesting table content.
    Multiple test are chained in the same function to improve test performances.
    """

    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    table, _, _, _, _ = setup_interesting_test_table(
        data_fixture,
        user,
    )
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )

    service = data_fixture.create_local_baserow_get_row_service(
        integration=integration,
        table=table,
        filter_type="OR",
    )

    dispatch_context = FakeDispatchContext()

    # Normal dispatch
    result = service.get_type().dispatch(service, dispatch_context)

    assert len(result.data.keys()) == table.field_set.count() + 2

    # Now can we dispatch the table if all fields are hidden?
    field_names = {
        "all": {service.id: ["id"]},
        "external": {service.id: ["id"]},
        "internal": {},
    }

    dispatch_context = FakeDispatchContext(public_allowed_properties=field_names)

    # If this dispatch doesn't fail while all the fields are excluded from the result
    # means that the enhance_by_field is filtered to only used field.
    result = service.get_type().dispatch(service, dispatch_context)

    assert len(result.data.keys()) == 1 + 1  # We also have the order at that point

    # Test with a filter on a single select field. Single select have a select_related
    single_select_field = table.field_set.get(name="single_select")
    service_filter = data_fixture.create_local_baserow_table_service_filter(
        service=service,
        field=single_select_field,
        value="'A'",
        order=0,
    )

    dispatch_context = FakeDispatchContext(public_allowed_properties=field_names)

    assert len(result.data.keys()) == 1 + 1

    # Let's remove the filter to not interfer with the sort
    service_filter.delete()

    # Test with a sort
    service_sort = data_fixture.create_local_baserow_table_service_sort(
        service=service, field=single_select_field, order_by=SORT_ORDER_ASC, order=0
    )

    dispatch_context = FakeDispatchContext(public_allowed_properties=field_names)
    assert len(result.data.keys()) == 1 + 1

    service_sort.delete()

    # Now with a search
    service.search_query = "'A'"
    service.save()

    dispatch_context = FakeDispatchContext(public_allowed_properties=field_names)
    assert len(result.data.keys()) == 1 + 1
