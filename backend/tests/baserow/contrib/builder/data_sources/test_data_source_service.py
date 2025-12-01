from decimal import Decimal
from unittest.mock import MagicMock, PropertyMock, patch

from django.http import HttpRequest

import pytest

from baserow.contrib.builder.data_sources.builder_dispatch_context import (
    BuilderDispatchContext,
)
from baserow.contrib.builder.data_sources.exceptions import (
    DataSourceDoesNotExist,
    DataSourceNotInSamePage,
)
from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.data_sources.service import DataSourceService
from baserow.contrib.builder.pages.exceptions import PageNotInBuilder
from baserow.contrib.database.views.view_filters import EqualViewFilterType
from baserow.core.exceptions import PermissionException
from baserow.core.services.exceptions import (
    InvalidServiceTypeDispatchSource,
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.models import Service
from baserow.core.services.registries import DispatchTypes, service_type_registry
from baserow.test_utils.helpers import AnyStr


@pytest.mark.django_db
@patch("baserow.contrib.builder.data_sources.service.data_source_created")
def test_create_data_source(data_source_created_mock, data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_source1 = data_fixture.create_builder_data_source(page=page, order="1.0000")
    data_source3 = data_fixture.create_builder_data_source(page=page, order="2.0000")

    service_type = service_type_registry.get("local_baserow_get_row")

    service = DataSourceService()
    data_source = service.create_data_source(user, service_type=service_type, page=page)

    last_data_source = DataSource.objects.last()

    # Check it's the last data_source
    assert last_data_source.id == data_source.id

    data_source_created_mock.send.assert_called_once_with(
        service, data_source=data_source, user=user, before_id=None
    )


@pytest.mark.django_db
def test_create_data_source_before(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_source1 = data_fixture.create_builder_data_source(page=page, order="1.0000")
    data_source3 = data_fixture.create_builder_data_source(page=page, order="2.0000")

    service_type = service_type_registry.get("local_baserow_get_row")

    data_source2 = DataSourceService().create_data_source(
        user, service_type=service_type, page=page, before=data_source3
    )

    data_sources = DataSource.objects.all()
    assert data_sources[0].id == data_source1.id
    assert data_sources[1].id == data_source2.id
    assert data_sources[2].id == data_source3.id


@pytest.mark.django_db
def test_create_data_source_before_not_same_page(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_source1 = data_fixture.create_builder_data_source(page=page, order="1.0000")
    data_source3 = data_fixture.create_builder_data_source(order="2.0000")

    service_type = service_type_registry.get("local_baserow_get_row")

    with pytest.raises(DataSourceNotInSamePage):
        DataSourceService().create_data_source(
            user, service_type=service_type, page=page, before=data_source3
        )


@pytest.mark.django_db
def test_create_data_source_with_service_type_for_different_dispatch_type(
    data_fixture,
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)

    service_type = service_type_registry.get("local_baserow_upsert_row")

    assert not service_type.can_be_dispatched_as(DispatchTypes.DATA)

    with pytest.raises(InvalidServiceTypeDispatchSource):
        DataSourceService().create_data_source(
            user, service_type=service_type, page=page
        )


@pytest.mark.django_db
def test_get_unique_orders_before_data_source_triggering_full_page_order_reset(
    data_fixture,
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_source_1 = data_fixture.create_builder_data_source(
        page=page, order="1.00000000000000000000"
    )
    data_source_2 = data_fixture.create_builder_data_source(
        page=page, order="1.00000000000000001000"
    )
    data_source_3 = data_fixture.create_builder_data_source(
        page=page, order="2.99999999999999999999"
    )
    data_source_4 = data_fixture.create_builder_data_source(
        page=page, order="2.99999999999999999998"
    )

    service_type = service_type_registry.get("local_baserow_get_row")

    data_source_created = DataSourceService().create_data_source(
        user, service_type=service_type, page=page, before=data_source_3
    )

    data_source_1.refresh_from_db()
    data_source_2.refresh_from_db()
    data_source_3.refresh_from_db()
    data_source_4.refresh_from_db()

    assert data_source_1.order == Decimal("1.00000000000000000000")
    assert data_source_2.order == Decimal("2.00000000000000000000")
    assert data_source_4.order == Decimal("3.00000000000000000000")
    assert data_source_3.order == Decimal("4.00000000000000000000")
    assert data_source_created.order == Decimal("3.50000000000000000000")


@pytest.mark.django_db
@patch("baserow.contrib.builder.data_sources.service.data_source_orders_recalculated")
def test_recalculate_full_order(data_source_orders_recalculated_mock, data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_fixture.create_builder_data_source(page=page, order="1.9000")
    data_fixture.create_builder_data_source(page=page, order="3.4000")

    service = DataSourceService()
    service.recalculate_full_orders(user, page)

    data_source_orders_recalculated_mock.send.assert_called_once_with(
        service, page=page
    )


@pytest.mark.django_db
def test_create_data_source_permission_denied(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)

    service_type = service_type_registry.get("local_baserow_get_row")

    with stub_check_permissions(raise_permission_denied=True), pytest.raises(
        PermissionException
    ):
        DataSourceService().create_data_source(
            user,
            service_type=service_type,
            page=page,
        )


@pytest.mark.django_db
def test_get_data_source(data_fixture):
    user = data_fixture.create_user()
    data_source = data_fixture.create_builder_data_source(user=user)

    assert (
        DataSourceService().get_data_source(user, data_source.id).id == data_source.id
    )


@pytest.mark.django_db
def test_get_data_source_does_not_exist(data_fixture):
    user = data_fixture.create_user()

    with pytest.raises(DataSourceDoesNotExist):
        assert DataSourceService().get_data_source(user, 0)


@pytest.mark.django_db
def test_get_data_source_permission_denied(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    data_source = data_fixture.create_builder_data_source(user=user)

    with stub_check_permissions(raise_permission_denied=True), pytest.raises(
        PermissionException
    ):
        DataSourceService().get_data_source(user, data_source.id)


@pytest.mark.django_db
def test_get_data_sources(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_source1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page, user=user
    )
    data_source2 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page, user=user
    )
    data_source3 = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page, user=user
    )

    assert DataSource.objects.count() == 3
    assert Service.objects.count() == 3

    assert [p.id for p in DataSourceService().get_data_sources(user, page)] == [
        data_source1.id,
        data_source2.id,
        data_source3.id,
    ]

    def exclude_data_source_1(
        actor,
        operation_name,
        queryset,
        workspace=None,
        context=None,
    ):
        return queryset.exclude(id=data_source1.id)

    with stub_check_permissions() as stub:
        stub.filter_queryset = exclude_data_source_1

        assert [p.id for p in DataSourceService().get_data_sources(user, page)] == [
            data_source2.id,
            data_source3.id,
        ]


@pytest.mark.django_db
@patch("baserow.contrib.builder.data_sources.service.data_source_deleted")
def test_delete_data_source(data_source_deleted_mock, data_fixture):
    user = data_fixture.create_user()
    data_source = data_fixture.create_builder_data_source(user=user)

    service = DataSourceService()
    service.delete_data_source(user, data_source)

    data_source_deleted_mock.send.assert_called_once_with(
        service, data_source_id=data_source.id, page=data_source.page, user=user
    )


@pytest.mark.django_db(transaction=True)
def test_delete_data_source_permission_denied(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    data_source = data_fixture.create_builder_data_source(user=user)

    with stub_check_permissions(raise_permission_denied=True), pytest.raises(
        PermissionException
    ):
        DataSourceService().delete_data_source(user, data_source)


@pytest.mark.django_db
@patch("baserow.contrib.builder.data_sources.service.data_source_updated")
def test_update_data_source(data_source_updated_mock, data_fixture):
    user = data_fixture.create_user()
    data_source = data_fixture.create_builder_data_source(user=user)

    service = DataSourceService()
    data_source_updated = service.update_data_source(
        user, data_source, value="newValue"
    )

    data_source_updated_mock.send.assert_called_once_with(
        service, data_source=data_source_updated, user=user
    )


@pytest.mark.django_db
def test_update_data_source_external_page(data_fixture):
    user = data_fixture.create_user()
    data_source = data_fixture.create_builder_data_source(user=user)
    page_not_on_same_builder = data_fixture.create_builder_page(user=user)

    with pytest.raises(PageNotInBuilder):
        DataSourceService().update_data_source(
            user, data_source, page=page_not_on_same_builder
        )


@pytest.mark.django_db(transaction=True)
def test_update_data_source_permission_denied(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    data_source = data_fixture.create_builder_data_source(user=user)

    with stub_check_permissions(raise_permission_denied=True), pytest.raises(
        PermissionException
    ):
        DataSourceService().update_data_source(user, data_source, value="newValue")


@pytest.mark.django_db
def test_update_data_source_with_service_type_for_different_dispatch_type(
    data_fixture,
):
    user = data_fixture.create_user()
    data_source = data_fixture.create_builder_data_source(user=user)

    new_service_type = service_type_registry.get("local_baserow_upsert_row")
    assert not new_service_type.can_be_dispatched_as(DispatchTypes.DATA)

    with pytest.raises(InvalidServiceTypeDispatchSource):
        DataSourceService().update_data_source(
            user, data_source, new_service_type=new_service_type
        )


@pytest.mark.django_db
@patch("baserow.contrib.builder.data_sources.service.data_source_moved")
def test_move_data_source(data_source_moved_mock, data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_source1 = data_fixture.create_builder_data_source(page=page)
    data_source2 = data_fixture.create_builder_data_source(page=page)
    data_source3 = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page
    )

    service = DataSourceService()
    data_source_moved = service.move_data_source(
        user, data_source3, before=data_source2
    )

    data_source_moved_mock.send.assert_called_once_with(
        service, data_source=data_source_moved, before=data_source2, user=user
    )


@pytest.mark.django_db
def test_move_data_source_not_same_page(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    page2 = data_fixture.create_builder_page(user=user)
    data_source1 = data_fixture.create_builder_data_source(page=page)
    data_source2 = data_fixture.create_builder_data_source(page=page)
    data_source3 = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page2
    )

    with pytest.raises(DataSourceNotInSamePage):
        DataSourceService().move_data_source(user, data_source3, before=data_source2)


@pytest.mark.django_db
def test_move_data_source_permission_denied(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_source1 = data_fixture.create_builder_data_source(page=page)
    data_source2 = data_fixture.create_builder_data_source(page=page)
    data_source3 = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page
    )

    with stub_check_permissions(raise_permission_denied=True), pytest.raises(
        PermissionException
    ):
        DataSourceService().move_data_source(user, data_source3, before=data_source2)


@pytest.mark.django_db
@patch("baserow.contrib.builder.data_sources.service.data_source_orders_recalculated")
def test_move_data_source_trigger_order_recalculed(
    data_source_orders_recalculated_mock, data_fixture
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_source1 = data_fixture.create_builder_data_source(
        page=page, order="2.99999999999999999998"
    )
    data_source2 = data_fixture.create_builder_data_source(
        page=page, order="2.99999999999999999999"
    )
    data_source3 = data_fixture.create_builder_data_source(page=page, order="3.0000")

    service = DataSourceService()
    service.move_data_source(user, data_source3, before=data_source2)

    data_source_orders_recalculated_mock.send.assert_called_once_with(
        service, page=page
    )


@pytest.mark.django_db
def test_dispatch_data_source(data_fixture):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("My Color", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
            ["Audi", "Orange"],
            ["Volkswagen", "White"],
            ["Volkswagen", "Green"],
        ],
    )
    view = data_fixture.create_grid_view(user, table=table)
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table,
        row_id="2",
    )

    dispatch_context = BuilderDispatchContext(
        HttpRequest(), page, only_expose_public_allowed_properties=False
    )
    result = DataSourceService().dispatch_data_source(
        user, data_source, dispatch_context
    )

    assert result == {
        "id": rows[1].id,
        "order": AnyStr(),
        fields[0].name: "Audi",
        fields[1].name: "Orange",
    }


@pytest.mark.django_db
def test_dispatch_page_data_sources(data_fixture):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("My Color", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
            ["Audi", "Orange"],
            ["Volkswagen", "White"],
            ["Volkswagen", "Green"],
        ],
    )
    view = data_fixture.create_grid_view(user, table=table)
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table,
        row_id="2",
    )
    data_source2 = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table,
        row_id="3",
    )
    data_source3 = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table,
        row_id="b",
    )

    dispatch_context = BuilderDispatchContext(
        HttpRequest(), page, only_expose_public_allowed_properties=False
    )
    result = DataSourceService().dispatch_page_data_sources(
        user, page, dispatch_context
    )

    assert result[data_source.id] == {
        "id": rows[1].id,
        "order": AnyStr(),
        fields[0].name: "Audi",
        fields[1].name: "Orange",
    }

    assert result[data_source2.id] == {
        "id": rows[2].id,
        "order": AnyStr(),
        fields[0].name: "Volkswagen",
        fields[1].name: "White",
    }

    assert isinstance(result[data_source3.id], Exception)


@pytest.mark.django_db
def test_dispatch_data_source_permission_denied(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("My Color", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
        ],
    )
    view = data_fixture.create_grid_view(user, table=table)
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table,
        row_id="1",
    )

    dispatch_context = BuilderDispatchContext(
        HttpRequest(), page, only_expose_public_allowed_properties=False
    )

    with stub_check_permissions(raise_permission_denied=True), pytest.raises(
        PermissionException
    ):
        DataSourceService().dispatch_data_source(user, data_source, dispatch_context)


@pytest.mark.django_db
def test_dispatch_data_source_improperly_configured(data_fixture):
    user = data_fixture.create_user()

    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=None,
    )

    # Without type
    data_source = data_fixture.create_builder_data_source(
        user=user, page=page, integration=integration
    )

    dispatch_context = BuilderDispatchContext(
        HttpRequest(), page, only_expose_public_allowed_properties=False
    )

    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        DataSourceService().dispatch_data_source(user, data_source, dispatch_context)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "data_source_row_ids",
    (
        ["1"],
        ["1", "2"],
        ["1", "2", "3"],
    ),
)
def test_dispatch_data_sources_excludes_unused_fields_in_non_list_data_sources(
    data_fixture, data_source_row_ids
):
    """
    Test the dispatch_data_sources() method when using Get Row. Ensure that
    any unused data sources are excluded from the results.
    """

    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Candy", "text"),
            ("Category", "text"),
        ],
        rows=[
            ["Fruit Roll-up", "Fruit leather"],
            ["Gobstopper", "Hard candy"],
            ["Twix", "Chocolate biscuit"],
        ],
    )

    view = data_fixture.create_grid_view(user, table=table)
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)

    data_sources = []

    # We want to test that only some of the data sources are returned, thus
    # we need to create multiple data sources for this page.
    #
    # We use the same table with a different row_id for each data source.
    for row_id in data_source_row_ids:
        data_sources.append(
            data_fixture.create_builder_local_baserow_get_row_data_source(
                user=user,
                page=page,
                integration=integration,
                view=view,
                table=table,
                row_id=row_id,
            )
        )

    # We are testing the logic that excludes fields from the results.
    # We aren't testing how the field names themselves are derived; that is
    # tested elsewhere.
    #
    # To simplify the test, we are mocking the allowed field names. The
    # alternative is to create an Element with a formula for each data
    # source we want to test.
    field_names = [field.db_column for field in fields]
    internal_allowed_properties = {
        data_source.service.id: field_names for data_source in data_sources
    }

    with patch(
        "baserow.contrib.builder.data_sources.builder_dispatch_context.BuilderDispatchContext.public_allowed_properties",
        new_callable=PropertyMock,
    ) as mock_public_allowed_properties:
        mock_public_allowed_properties.return_value = {
            "internal": internal_allowed_properties,
            "external": {},
            "all": internal_allowed_properties,
        }
        dispatch_context = BuilderDispatchContext(
            HttpRequest(), page, only_expose_public_allowed_properties=True
        )
        result = DataSourceService().dispatch_data_sources(
            user, data_sources, dispatch_context
        )

    # Ensure that the results size equals the number of data sources used
    # in the page.
    assert len(result.keys()) == len(data_sources)

    # Ensure field_names are not in the returned result for security reasons.
    for data_source in data_sources:
        row = result[data_source.id]
        for field in fields:
            assert field.db_column not in row


@pytest.mark.django_db
@pytest.mark.parametrize(
    "data_source_fruit_names", (["Fruit Roll-up", "Gobstopper", "Twix"],)
)
def test_dispatch_data_sources_excludes_unused_fields_in_list_data_sources(
    data_fixture, data_source_fruit_names
):
    """
    Test the dispatch_data_sources() method when using List Rows. Ensure that
    any unused data sources are excluded from the results.
    """

    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Candy", "text"),
            ("Category", "text"),
        ],
        rows=[
            ["Fruit Roll-up", "Fruit leather"],
            ["Gobstopper", "Hard candy"],
            ["Twix", "Chocolate biscuit"],
        ],
    )

    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)

    data_sources = []

    # We want to test that only some of the data sources are returned, thus
    # we need to create multiple data sources for this page.
    #
    # We use the same table with a search filter to target a different row
    # for each data source.
    for fruit_name in data_source_fruit_names:
        data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
            user=user, page=page, table=table, integration=integration
        )

        data_fixture.create_local_baserow_table_service_filter(
            service=data_source.service,
            field=fields[0],
            value=fruit_name,
            type=EqualViewFilterType.type,
            value_is_formula=False,
        )
        data_sources.append(data_source)

    # We are testing the logic that excludes fields from the results.
    # We aren't testing how the field names themselves are derived; that is
    # tested elsewhere.
    #
    # To simplify the test, we are mocking the allowed field names. The
    # alternative is to create an Element with a formula for each data
    # source we want to test.
    field_names = [f"field_{field.id}" for field in fields]
    internal_allowed_properties = {
        data_source.service.id: field_names for data_source in data_sources
    }

    with patch(
        "baserow.contrib.builder.data_sources.service.BuilderDispatchContext.public_allowed_properties",
        new_callable=PropertyMock,
    ) as mock_public_allowed_properties:
        mock_public_allowed_properties.return_value = {
            "internal": internal_allowed_properties,
            "external": {},
            "all": internal_allowed_properties,
        }
        dispatch_context = BuilderDispatchContext(
            HttpRequest(), page, only_expose_public_allowed_properties=True
        )
        result = DataSourceService().dispatch_data_sources(
            user, data_sources, dispatch_context
        )

    # Ensure the non public fields aren't in the result
    for data_source in data_sources:
        ds_result = result[data_source.id]
        assert ds_result == {
            "has_next_page": False,
            "results": [{}],
        }


@pytest.mark.django_db
def test_dispatch_data_sources_skips_exceptions_in_results(data_fixture):
    """
    Test the dispatch_data_sources() method when the results contain an exception.

    If a Data Source ID's value is an exception, the same exception should be
    returned in the results, without being modified.
    """

    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)

    data_source_1 = MagicMock()
    data_source_1.id = 100
    data_source_1.service.id = 200
    data_source_2 = MagicMock()
    data_source_2.id = 101
    data_source_2.service.id = 201
    data_sources = [data_source_1, data_source_2]

    expected_error = ValueError("Foo Error")

    with patch(
        "baserow.contrib.builder.data_sources.service.BuilderDispatchContext.public_allowed_properties",
        new_callable=PropertyMock,
    ) as mock_public_allowed_properties:
        # Any non None return value is sufficient, so that the test can reach
        # the for-loop of data_sources.
        mock_public_allowed_properties.return_value = {
            "external": {
                200: ["field_1"],
                201: ["field_2"],
            }
        }

        results = {
            data_source_1.id: {
                "results": [
                    {
                        "id": 300,
                        "order": "1.0",
                        "field_1": "foo",
                    }
                ]
            },
            data_source_2.id: expected_error,
        }
        service = DataSourceService()
        service.handler.dispatch_data_sources = MagicMock(return_value=results)

        dispatch_context = BuilderDispatchContext(
            HttpRequest(), page, only_expose_public_allowed_properties=True
        )
        result = service.dispatch_data_sources(user, data_sources, dispatch_context)

    assert result[data_source_2.id] == expected_error
