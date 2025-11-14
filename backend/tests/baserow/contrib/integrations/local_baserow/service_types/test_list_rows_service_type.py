from collections import defaultdict
from unittest.mock import MagicMock, Mock, patch

from django.test import override_settings

import pytest

from baserow.contrib.builder.data_sources.service import DataSourceService
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.elements.service import ElementService
from baserow.contrib.builder.pages.service import PageService
from baserow.contrib.database.api.rows.serializers import RowSerializer
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.views.models import SORT_ORDER_ASC, SORT_ORDER_DESC
from baserow.contrib.database.views.view_filters import MultipleSelectHasViewFilterType
from baserow.contrib.integrations.local_baserow.models import LocalBaserowListRows
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowListRowsUserServiceType,
)
from baserow.core.exceptions import PermissionException
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.registries import service_type_registry
from baserow.core.utils import MirrorDict
from baserow.test_utils.helpers import AnyStr, setup_interesting_test_table
from baserow.test_utils.pytest_conftest import FakeDispatchContext, fake_import_formula


@pytest.mark.django_db
def test_create_local_baserow_list_rows_service(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    view = data_fixture.create_grid_view(user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )

    service_type = service_type_registry.get("local_baserow_list_rows")

    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
        },
        user,
    )

    service = ServiceHandler().create_service(service_type, **values)

    assert service.view.id == view.id
    assert service.table.id == view.table_id


@pytest.mark.django_db
def test_export_import_local_baserow_list_rows_service(data_fixture):
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
    view = data_fixture.create_grid_view(user, table=table)
    service_type = service_type_registry.get("local_baserow_list_rows")
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    service = data_fixture.create_local_baserow_list_rows_service(
        integration=integration,
        view=view,
        table=view.table,
        search_query="get('page_parameter.id')",
        filter_type="OR",
        default_result_count=50,
    )

    field = fields[0]
    service_filter = data_fixture.create_local_baserow_table_service_filter(
        service=service,
        field=field,
        value="get('page_parameter.filter')",
        order=0,
    )
    service_sort = data_fixture.create_local_baserow_table_service_sort(
        service=service, field=field, order_by=SORT_ORDER_ASC, order=0
    )

    exported = service_type.export_serialized(service)

    assert exported == {
        "id": service.id,
        "type": service_type.type,
        "view_id": service.view_id,
        "table_id": service.table_id,
        "integration_id": service.integration_id,
        "search_query": service.search_query,
        "filter_type": "OR",
        "default_result_count": 50,
        "sample_data": None,
        "filters": [
            {
                "field_id": service_filter.field_id,
                "type": service_filter.type,
                "value": service_filter.value,
                "value_is_formula": service_filter.value_is_formula,
            }
        ],
        "sortings": [
            {
                "field_id": service_sort.field_id,
                "order_by": service_sort.order_by,
            }
        ],
    }

    id_mapping = {}

    service: LocalBaserowListRows = service_type.import_serialized(  # type: ignore
        integration, exported, id_mapping, import_formula=fake_import_formula
    )

    assert service.id != exported["id"]
    assert service.view_id == exported["view_id"]
    assert service.table_id == exported["table_id"]
    assert service.filter_type == exported["filter_type"]
    assert service.search_query == exported["search_query"]
    assert service.integration_id == exported["integration_id"]
    assert service.default_result_count == exported["default_result_count"]
    assert isinstance(service, service_type.model_class)

    assert service.service_filters.count() == 1
    service_filter = service.service_filters.get()
    assert service_filter.type == exported["filters"][0]["type"]
    assert service_filter.value == exported["filters"][0]["value"]
    assert service_filter.field_id == exported["filters"][0]["field_id"]
    assert service_filter.value_is_formula == exported["filters"][0]["value_is_formula"]

    assert service.service_sorts.count() == 1
    service_sort = service.service_sorts.get()
    assert service_sort.field_id == exported["sortings"][0]["field_id"]
    assert service_sort.order_by == exported["sortings"][0]["order_by"]

    view_2 = data_fixture.create_grid_view(user, table=table)
    field_2 = data_fixture.create_text_field(order=1, table=table)
    table_2, _, _ = data_fixture.build_table(
        columns=[("Number", "number")], rows=[[1]], user=user
    )

    id_mapping = defaultdict(lambda: MirrorDict())
    id_mapping["database_views"] = {view.id: view_2.id}  # type: ignore
    id_mapping["database_fields"] = {field.id: field_2.id}  # type: ignore
    id_mapping["database_tables"] = {table.id: table_2.id}  # type: ignore
    service: LocalBaserowListRows = service_type.import_serialized(  # type: ignore
        integration, exported, id_mapping, import_formula=fake_import_formula
    )

    assert service.view_id == view_2.id
    assert service.table_id == table_2.id

    service_filter = service.service_filters.get()
    assert service_filter.field_id == field_2.id

    service_sort = service.service_sorts.get()
    assert service_sort.field_id == field_2.id


@pytest.mark.django_db
def test_update_local_baserow_list_rows_service(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    view = data_fixture.create_grid_view(user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    service = data_fixture.create_local_baserow_list_rows_service(
        integration=integration, view=view, table=view.table, search_query="'badgers'"
    )

    service_type = service_type_registry.get("local_baserow_list_rows")

    values = service_type.prepare_values(
        {"view_id": None, "integration_id": None, "search_query": ""}, user
    )

    ServiceHandler().update_service(service_type, service, **values)

    service.refresh_from_db()

    assert service.specific.view is None
    assert service.specific.search_query["formula"] == ""
    assert service.specific.integration is None


@pytest.mark.django_db
def test_local_baserow_list_rows_service_dispatch_transform(data_fixture):
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

    service = data_fixture.create_local_baserow_list_rows_service(
        integration=integration,
        view=view,
        table=table,
    )

    service_type = LocalBaserowListRowsUserServiceType()

    dispatch_context = FakeDispatchContext()
    result = service_type.dispatch(service, dispatch_context)

    assert [dict(r) for r in result.data["results"]] == [
        {
            "id": rows[0].id,
            fields[0].name: "BMW",
            fields[1].name: "Blue",
            "order": AnyStr(),
        },
        {
            "id": rows[1].id,
            fields[0].name: "Audi",
            fields[1].name: "Orange",
            "order": AnyStr(),
        },
    ]
    assert result.data["has_next_page"] is False


@pytest.mark.django_db
def test_local_baserow_list_rows_service_dispatch_transform_with_default(data_fixture):
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
        ]
        * 50,
    )
    view = data_fixture.create_grid_view(user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )

    service = data_fixture.create_local_baserow_list_rows_service(
        integration=integration, view=view, table=table, default_result_count=5
    )

    service_type = LocalBaserowListRowsUserServiceType()

    result = service_type.dispatch(service, FakeDispatchContext(count=None))

    assert len(result.data["results"]) == 5

    result = service_type.dispatch(service, FakeDispatchContext(count=10))

    assert len(result.data["results"]) == 10

    with override_settings(INTEGRATION_LOCAL_BASEROW_PAGE_SIZE_LIMIT=30):
        result = service_type.dispatch(service, FakeDispatchContext(count=100))

        assert len(result.data["results"]) == 30

    service.default_result_count = 0
    service.save()

    result = service_type.dispatch(service, FakeDispatchContext(count=None))

    assert len(result.data["results"]) == 0


@pytest.mark.django_db
def test_local_baserow_list_rows_service_dispatch_data_permission_denied(
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
    view = data_fixture.create_grid_view(user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )

    service = data_fixture.create_local_baserow_list_rows_service(
        integration=integration,
        view=view,
        table=table,
    )

    dispatch_context = FakeDispatchContext()
    with stub_check_permissions(raise_permission_denied=True), pytest.raises(
        PermissionException
    ):
        LocalBaserowListRowsUserServiceType().dispatch_data(
            service, {"table": table}, dispatch_context
        )


@pytest.mark.django_db
def test_local_baserow_list_rows_service_before_dispatch_validation_error(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    service = data_fixture.create_local_baserow_list_rows_service(
        integration=integration, table=None
    )

    dispatch_context = FakeDispatchContext()
    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        LocalBaserowListRowsUserServiceType().resolve_service_formulas(
            service, dispatch_context
        )


@pytest.mark.django_db
def test_local_baserow_list_rows_service_dispatch_data_with_view_and_service_filters(
    data_fixture,
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user
    )
    database = data_fixture.create_database_application(workspace=builder.workspace)
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Ingredient", "text", {}),
        ],
    )
    field = table.field_set.get(name="Ingredient")
    [row_1, row_2, _] = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[
                {f"field_{field.id}": "Cheese"},
                {f"field_{field.id}": "Chicken"},
                {f"field_{field.id}": "Milk"},
            ],
        )
        .created_rows
    )

    view = data_fixture.create_grid_view(user, table=table, owned_by=user)
    data_fixture.create_view_filter(view=view, field=field, type="contains", value="Ch")

    service_type = LocalBaserowListRowsUserServiceType()
    service = data_fixture.create_local_baserow_list_rows_service(
        view=view, table=table, integration=integration
    )

    dispatch_context = FakeDispatchContext()
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    dispatch_data = service_type.dispatch_data(
        service, dispatch_values, dispatch_context
    )
    results = dispatch_data["results"]
    assert [r.id for r in results] == [row_1.id, row_2.id]

    data_fixture.create_local_baserow_table_service_filter(
        service=service,
        field=field,
        value="'Cheese'",
        order=0,
        value_is_formula=True,
    )

    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    dispatch_data = service_type.dispatch_data(
        service, dispatch_values, dispatch_context
    )
    results = dispatch_data["results"]
    assert [r.id for r in results] == [row_1.id]


@pytest.mark.django_db
def test_local_baserow_list_rows_service_dispatch_data_with_varying_filter_types(
    data_fixture,
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user
    )
    database = data_fixture.create_database_application(workspace=builder.workspace)
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Ingredient", "text", {}),
            ("Cost", "number", {}),
        ],
    )
    ingredient = table.field_set.get(name="Ingredient")
    cost = table.field_set.get(name="Cost")
    [row_1, row_2, row_3, _] = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[
                {f"field_{ingredient.id}": "Duck", f"field_{cost.id}": 50},
                {f"field_{ingredient.id}": "Duckling", f"field_{cost.id}": 25},
                {f"field_{ingredient.id}": "Goose", f"field_{cost.id}": 150},
                {f"field_{ingredient.id}": "Beef", f"field_{cost.id}": 250},
            ],
        )
        .created_rows
    )

    view = data_fixture.create_grid_view(
        user, table=table, owned_by=user, filter_type="OR"
    )

    dispatch_context = FakeDispatchContext()
    service_type = LocalBaserowListRowsUserServiceType()
    service = data_fixture.create_local_baserow_list_rows_service(
        view=view, table=table, integration=integration, filter_type="OR"
    )

    # (ingredient=Duck OR ingredient=Goose) AND (cost=150).
    equals_duck = data_fixture.create_view_filter(
        view=view, field=ingredient, type="equal", value="Duck"
    )
    equals_goose = data_fixture.create_view_filter(
        view=view, field=ingredient, type="equal", value="Goose"
    )
    cost_150 = data_fixture.create_local_baserow_table_service_filter(
        service=service, field=cost, value="'150'", order=0, value_is_formula=True
    )
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    dispatch_data = service_type.dispatch_data(
        service, dispatch_values, dispatch_context
    )
    results = dispatch_data["results"]
    assert [r.id for r in results] == [
        row_3.id,  # Only Goose has a cost of 150.
    ]
    cost_150.delete()
    equals_duck.delete()
    equals_goose.delete()

    # (ingredient contains Duck) AND (cost=25 OR cost=50).
    data_fixture.create_view_filter(
        view=view, field=ingredient, type="contains", value="Duck"
    )
    data_fixture.create_local_baserow_table_service_filter(
        service=service, field=cost, value="'25'", order=0, value_is_formula=True
    )
    data_fixture.create_local_baserow_table_service_filter(
        service=service, field=cost, value="'50'", order=0, value_is_formula=True
    )
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    dispatch_data = service_type.dispatch_data(
        service, dispatch_values, dispatch_context
    )
    results = dispatch_data["results"]
    assert [r.id for r in results] == [
        row_1.id,  # Duck
        row_2.id,  # Duckling
    ]


@pytest.mark.django_db
def test_local_baserow_list_rows_service_dispatch_data_with_view_and_service_sorts(
    data_fixture,
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user
    )
    database = data_fixture.create_database_application(workspace=builder.workspace)
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Ingredient", "text", {}),
            ("Cost", "number", {}),
        ],
    )
    ingredients = table.field_set.get(name="Ingredient")
    cost = table.field_set.get(name="Cost")
    [row_1, row_2, row_3] = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[
                {f"field_{ingredients.id}": "Duck", f"field_{cost.id}": 50},
                {f"field_{ingredients.id}": "Goose", f"field_{cost.id}": 150},
                {f"field_{ingredients.id}": "Beef", f"field_{cost.id}": 250},
            ],
        )
        .created_rows
    )
    view = data_fixture.create_grid_view(user, table=table, owned_by=user)
    service_type = LocalBaserowListRowsUserServiceType()
    service = data_fixture.create_local_baserow_list_rows_service(
        view=view, table=table, integration=integration
    )

    dispatch_context = FakeDispatchContext()
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)

    # A `ViewSort` alone.
    view_sort = data_fixture.create_view_sort(view=view, field=ingredients, order="ASC")
    dispatch_data = service_type.dispatch_data(
        service, dispatch_values, dispatch_context
    )
    results = dispatch_data["results"]
    assert [r.id for r in results] == [
        row_3.id,
        row_1.id,
        row_2.id,
    ]
    view_sort.delete()

    # A `ServiceSort` alone.
    service_sort = data_fixture.create_local_baserow_table_service_sort(
        service=service, field=cost, order_by=SORT_ORDER_DESC, order=0
    )
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    dispatch_data = service_type.dispatch_data(
        service, dispatch_values, dispatch_context
    )
    results = dispatch_data["results"]
    assert [r.id for r in results] == [
        row_3.id,
        row_2.id,
        row_1.id,
    ]
    service_sort.delete()

    # A `ViewSort` & `ServiceSort`, the latter is used.
    data_fixture.create_local_baserow_table_service_sort(
        service=service, field=cost, order_by=SORT_ORDER_ASC, order=0
    )
    data_fixture.create_view_sort(view=view, field=cost, order=SORT_ORDER_DESC)
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    dispatch_data = service_type.dispatch_data(
        service, dispatch_values, dispatch_context
    )
    results = dispatch_data["results"]
    assert [r.id for r in results] == [
        row_1.id,
        row_2.id,
        row_3.id,
    ]


@pytest.mark.django_db
def test_local_baserow_list_rows_service_dispatch_data_with_pagination(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user
    )
    database = data_fixture.create_database_application(workspace=builder.workspace)
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Ingredient", "text", {}),
        ],
    )
    field = table.field_set.get(name="Ingredient")
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": "Cheese"},
            {f"field_{field.id}": "Chicken"},
            {f"field_{field.id}": "Milk"},
            {f"field_{field.id}": "Salt"},
            {f"field_{field.id}": "Pepper"},
            {f"field_{field.id}": "Tomato"},
            {f"field_{field.id}": "Potato"},
            {f"field_{field.id}": "Cucumber"},
            {f"field_{field.id}": "Rice"},
            {f"field_{field.id}": "Beans"},
        ],
    )

    service_type = LocalBaserowListRowsUserServiceType()
    service = data_fixture.create_local_baserow_list_rows_service(
        table=table, integration=integration
    )

    dispatch_context = FakeDispatchContext()
    dispatch_data = service_type.dispatch_data(
        service, {"table": table}, dispatch_context
    )

    assert len(dispatch_data["results"]) == 10
    assert dispatch_data["has_next_page"] is False

    dispatch_context = FakeDispatchContext()

    dispatch_context.range = Mock()
    dispatch_context.range.return_value = [0, 5]

    dispatch_data = service_type.dispatch_data(
        service, {"table": table}, dispatch_context
    )

    assert len(dispatch_data["results"]) == 5
    assert dispatch_data["has_next_page"] is True

    dispatch_context.range.return_value = [5, 3]

    dispatch_data = service_type.dispatch_data(
        service, {"table": table}, dispatch_context
    )

    assert len(dispatch_data["results"]) == 3
    assert dispatch_data["has_next_page"] is True

    dispatch_context.range.return_value = [5, 5]

    dispatch_data = service_type.dispatch_data(
        service, {"table": table}, dispatch_context
    )

    assert len(dispatch_data["results"]) == 5
    assert dispatch_data["has_next_page"] is False

    dispatch_context.range.return_value = [5, 10]

    dispatch_data = service_type.dispatch_data(
        service, {"table": table}, dispatch_context
    )

    assert len(dispatch_data["results"]) == 5
    assert dispatch_data["has_next_page"] is False


@pytest.mark.django_db
def test_local_baserow_list_rows_service_import_context_path(data_fixture):
    local_baserow_list_rows_service = LocalBaserowListRowsUserServiceType()

    assert local_baserow_list_rows_service.import_context_path([], {}) == []
    assert local_baserow_list_rows_service.import_context_path(["id"], {}) == ["id"]
    assert local_baserow_list_rows_service.import_context_path(
        ["field_1", "value"], {"database_fields": {1: 2}}
    ) == ["field_2", "value"]


@pytest.mark.django_db
def test_import_datasource_provider_formula_using_list_rows_service_containing_no_row_or_field_fails_silently(
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
    service = data_fixture.create_local_baserow_list_rows_service(
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
def test_import_formula_local_baserow_list_rows_user_service_type(data_fixture):
    """
    Ensure that formulas are imported correctly when importing the
    LocalBaserowListRowsUserServiceType service type.
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
    service_type = service_type_registry.get("local_baserow_list_rows")
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        table=table, page=page
    )
    service = data_fixture.create_local_baserow_list_rows_service(
        integration=integration,
        view=view,
        table=view.table,
        search_query=f"get('data_source.{data_source.id}.0.{text_field.db_column}')",
        filter_type="OR",
    )

    data_fixture.create_local_baserow_table_service_filter(
        service=service,
        field=text_field,
        value=f"get('data_source.{data_source.id}.0.{text_field.db_column}')",
        value_is_formula=True,
        order=0,
    )
    data_fixture.create_local_baserow_table_service_filter(
        service=service,
        field=text_field,
        value=f"fooValue",
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
    assert (
        imported_service.search_query["formula"]
        == f"get('data_source.{data_source2.id}.0.{text_field.db_column}')"
    )

    imported_service_filter_0 = imported_service.service_filters.get(order=0)
    assert (
        imported_service_filter_0.value["formula"]
        == f"get('data_source.{data_source2.id}.0.{text_field.db_column}')"
    )
    assert imported_service_filter_0.value_is_formula is True

    imported_service_filter_1 = imported_service.service_filters.get(order=1)
    assert imported_service_filter_1.value["formula"] == "fooValue"
    assert imported_service_filter_1.value_is_formula is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path,database_fields,expected",
    [
        # The second list item is a valid field ID, but since there are no
        # database field mappings, the same path is returned.
        (
            [0, "field_123"],
            {},
            [0, "field_123"],
        ),
        # The second list item is a valid field ID, but since there are no
        # matching database field mappings, the same path is returned.
        (
            [0, "field_123"],
            {456: 789},
            [0, "field_123"],
        ),
        # The second list item is a valid field ID and matches a database field
        # mapping, as such the updated path is returned.
        (
            [0, "field_123"],
            {123: 456},
            [0, "field_456"],
        ),
        # Ensure the updated field along with the unchanged remaining parts of
        # the path are returned.
        (
            [0, "field_123", "foo", "bar"],
            {123: 456},
            [0, "field_456", "foo", "bar"],
        ),
        # If there is only one path item, this is not a valid row path.
        # Therefore ensure the path is returned without any changes.
        (
            ["field_123"],
            {123: 456},
            ["field_123"],
        ),
        # The second list item is "xfield_123", which doesn't start with
        # "field_", and thus isn't a valid field. Ensure it is returned
        # without any changes.
        (
            [0, "xfield_123"],
            {123: 456},
            [0, "xfield_123"],
        ),
    ],
)
def test_local_baserow_list_rows_user_service_type_import_path(
    path, database_fields, expected
):
    """
    Ensure the LocalBaserowListRowsUserServiceType::import_path() correctly
    updates the field_id's in the path.
    """

    service_type = LocalBaserowListRowsUserServiceType()
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

    service_type = LocalBaserowListRowsUserServiceType()

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


@pytest.mark.django_db
def test_can_dispatch_table_with_deleted_field(data_fixture):
    """
    Test that we can dispatch a table when a field has been deleted but still
    referenced in the dispatch_context public_properties because of the cache for
    instance.
    """

    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    table, fields, _ = data_fixture.build_table(
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

    service = data_fixture.create_local_baserow_list_rows_service(
        integration=integration,
        table=table,
        filter_type="OR",
    )

    field_names = {
        "all": {
            service.id: ["id", fields[0].db_column, fields[1].db_column],
        },
        "external": {service.id: ["id"]},
        "internal": {service.id: [fields[0].db_column, fields[1].db_column]},
    }

    # We delete the field but it should just be ignored.
    fields[1].delete()

    dispatch_context = FakeDispatchContext(public_allowed_properties=field_names)

    result = service.get_type().dispatch(service, dispatch_context)

    assert (
        len(result.data["results"][0].keys()) == 2 + 1
    )  # We also have the order at that point


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

    service = data_fixture.create_local_baserow_list_rows_service(
        integration=integration,
        table=table,
        filter_type="OR",
    )

    dispatch_context = FakeDispatchContext()

    # Normal dispatch
    result = service.get_type().dispatch(service, dispatch_context)

    assert len(result.data["results"]) == 2
    assert len(result.data["results"][0].keys()) == table.field_set.count() + 2

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

    assert (
        len(result.data["results"][0].keys()) == 1 + 1
    )  # We also have the order at that point

    # Test with a filter on a single select field. Single select have a select_related
    single_select_field = table.field_set.get(name="single_select")
    service_filter = data_fixture.create_local_baserow_table_service_filter(
        service=service,
        field=single_select_field,
        type="not_equal",
        value="'Nothing'",
        value_is_formula=True,
        order=0,
    )

    dispatch_context = FakeDispatchContext(public_allowed_properties=field_names)

    result = service.get_type().dispatch(service, dispatch_context)

    assert len(result.data["results"][0].keys()) == 2 + 1

    # Let's remove the filter to not interfere with the sort
    service_filter.delete()

    # Test with a sort
    service_sort = data_fixture.create_local_baserow_table_service_sort(
        service=service, field=single_select_field, order_by=SORT_ORDER_ASC, order=0
    )

    dispatch_context = FakeDispatchContext(public_allowed_properties=field_names)

    result = service.get_type().dispatch(service, dispatch_context)

    assert len(result.data["results"][0].keys()) == 2 + 1

    service_sort.delete()

    # Now with a search query
    service.search_query = "1"
    service.save()

    dispatch_context = FakeDispatchContext(public_allowed_properties=field_names)

    result = service.get_type().dispatch(service, dispatch_context)

    assert len(result.data["results"][0].keys()) == 1 + 1


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
    Test the LocalBaserowListRowsUserServiceType::dispatch_transform() method.

    Ensure that the field_ids parameter is passed to the serializer class.
    """

    mock_serializer_instance = MagicMock()
    mock_serializer = MagicMock(return_value=mock_serializer_instance)
    mock_serializer.data = []
    mock_get_serializer.return_value = mock_serializer

    service_type = LocalBaserowListRowsUserServiceType()

    dispatch_data = {
        "baserow_table_model": MagicMock(),
        "results": [],
        "has_next_page": False,
    }

    dispatch_data["public_allowed_properties"] = field_names

    results = service_type.dispatch_transform(dispatch_data)

    assert results.data == {
        "has_next_page": False,
        "results": mock_serializer.data,
    }
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
            ["field_456", "0", "value"],
            ["field_456"],
        ),
        (
            ["field_456", "0", "value", "", "", ""],
            ["field_456"],
        ),
    ],
)
def test_extract_properties(path, expected):
    """
    Test the extract_properties() method.
    """

    service_type = LocalBaserowListRowsUserServiceType()

    result = service_type.extract_properties(path)

    assert result == expected


@pytest.mark.django_db(transaction=True)
def test_search_on_multiple_select_with_list(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    page = data_fixture.create_builder_page(
        user=user, path="/page/", query_params=[{"name": "foobar", "type": "numeric"}]
    )

    service_type = service_type_registry.get("local_baserow_list_rows")
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(user, table=table)
    option_field = data_fixture.create_multiple_select_field(
        table=table, name="option_field", order=1, primary=True
    )
    options = [
        data_fixture.create_select_option(
            field=option_field, value="A", color="AAA", order=0
        ),
        data_fixture.create_select_option(
            field=option_field, value="B", color="BBB", order=0
        ),
        data_fixture.create_select_option(
            field=option_field, value="C", color="CCC", order=0
        ),
    ]
    table_rows = data_fixture.create_rows_in_table(
        table=table,
        rows=[[(options[0].id,)], [(options[1].id,)], [(options[1].id,)]],
        fields=[option_field],
    )

    service = data_fixture.create_local_baserow_list_rows_service(
        integration=integration,
        view=view,
        table=view.table,
        search_query="",
        filter_type="OR",
    )

    data_fixture.create_local_baserow_table_service_filter(
        service=service,
        field=option_field,
        value="get('foobar')",
        order=0,
        type=MultipleSelectHasViewFilterType.type,
        value_is_formula=True,
    )

    dispatch_context = FakeDispatchContext(context={"foobar": [options[0].id]})
    dispatch_data = service_type.dispatch_data(
        service, {"table": table}, dispatch_context
    )
    assert len(dispatch_data["results"]) == 1
    assert dispatch_data["results"][0]._primary_field_id == options[0].field_id
