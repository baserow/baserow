from decimal import Decimal
from unittest.mock import patch

from django.http import HttpRequest
from django.shortcuts import reverse

import pytest

from baserow.contrib.builder.data_sources.builder_dispatch_context import (
    BuilderDispatchContext,
)
from baserow.contrib.builder.data_sources.exceptions import DataSourceDoesNotExist
from baserow.contrib.builder.data_sources.handler import DataSourceHandler
from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowGetRow,
    LocalBaserowListRows,
)
from baserow.core.exceptions import CannotCalculateIntermediateOrder
from baserow.core.services.registries import service_type_registry
from baserow.core.user_sources.user_source_user import UserSourceUser
from baserow.test_utils.helpers import AnyStr
from tests.baserow.contrib.builder.api.user_sources.helpers import (
    create_user_table_and_role,
)


@pytest.mark.django_db
def test_create_data_source(data_fixture):
    page = data_fixture.create_builder_page()

    service_type = service_type_registry.get("local_baserow_get_row")

    data_source = DataSourceHandler().create_data_source(page=page, name="Data source")

    assert data_source.page.id == page.id

    assert data_source.order == 1
    assert DataSource.objects.count() == 1

    data_source = DataSourceHandler().create_data_source(
        page=page, name="Data source 1", service_type=service_type
    )

    assert data_source.order == 2
    assert isinstance(data_source.service, LocalBaserowGetRow)
    assert data_source.name == "Data source 1"
    assert DataSource.objects.count() == 2


@pytest.mark.django_db
def test_get_data_source(data_fixture):
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source()
    assert DataSourceHandler().get_data_source(data_source.id).id == data_source.id


@pytest.mark.django_db
def test_get_data_source_does_not_exist(data_fixture):
    with pytest.raises(DataSourceDoesNotExist):
        assert DataSourceHandler().get_data_source(0)


@pytest.mark.django_db
@pytest.mark.parametrize("specific", [True, False])
def test_get_data_sources(data_fixture, specific):
    page = data_fixture.create_builder_page()
    data_source1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )
    data_source2 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )
    data_source3 = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page
    )
    data_source4 = data_fixture.create_builder_data_source(page=page)

    data_sources = DataSourceHandler().get_data_sources(page, specific=specific)

    assert [e.id for e in data_sources] == [
        data_source1.id,
        data_source2.id,
        data_source3.id,
        data_source4.id,
    ]

    if specific:
        assert isinstance(data_sources[0].service, LocalBaserowGetRow)
        assert isinstance(data_sources[2].service, LocalBaserowListRows)

    assert data_sources[3].service is None


@pytest.mark.django_db
def test_get_data_sources_with_shared(data_fixture):
    page = data_fixture.create_builder_page()
    shared_page = page.builder.shared_page
    data_source1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )
    data_source2 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )
    data_source3 = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page
    )
    data_source4 = data_fixture.create_builder_data_source(page=page)

    shared_data_source = data_fixture.create_builder_data_source(page=shared_page)
    shared_data_source2 = (
        data_fixture.create_builder_local_baserow_list_rows_data_source(
            page=shared_page
        )
    )

    data_sources = DataSourceHandler().get_data_sources(page, with_shared=True)

    assert [e.id for e in data_sources] == [
        shared_data_source.id,
        shared_data_source2.id,
        data_source1.id,
        data_source2.id,
        data_source3.id,
        data_source4.id,
    ]

    assert isinstance(data_sources[2].service, LocalBaserowGetRow)
    assert isinstance(data_sources[4].service, LocalBaserowListRows)
    assert data_sources[5].service is None


@pytest.mark.django_db
def test_delete_data_source(data_fixture):
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source()

    DataSourceHandler().delete_data_source(data_source)

    assert DataSource.objects.count() == 0


@pytest.mark.django_db
def test_update_data_source(data_fixture):
    user = data_fixture.create_user()
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user
    )

    service_type = service_type_registry.get("local_baserow_get_row")

    data_source_updated = DataSourceHandler().update_data_source(
        data_source, service_type, name="newValue"
    )

    assert data_source_updated.name == "newValue"


@pytest.mark.django_db
def test_update_data_source_change_type(data_fixture):
    user = data_fixture.create_user()
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user
    )

    service_type = service_type_registry.get("local_baserow_get_row")
    new_service_type = service_type_registry.get("local_baserow_list_rows")

    data_source_updated = DataSourceHandler().update_data_source(
        data_source, service_type, new_service_type=new_service_type
    )

    assert (
        service_type_registry.get_by_model(data_source_updated.service).type
        == "local_baserow_list_rows"
    )

    data_source_updated = DataSourceHandler().update_data_source(
        data_source, service_type, new_service_type=None
    )

    assert data_source_updated.service is None


@pytest.mark.django_db
def test_update_data_source_change_page(data_fixture):
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        name="No conflict"
    )
    page_dest = data_fixture.create_builder_page(builder=data_source.page.builder)

    data_source_updated = DataSourceHandler().update_data_source(
        data_source, page=page_dest
    )

    data_source_updated.refresh_from_db()

    assert data_source_updated.page_id == page_dest.id
    assert data_source_updated.name == "No conflict"


@pytest.mark.django_db
def test_update_data_source_change_page_with_conflict(data_fixture):
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        name="Conflict"
    )
    page_dest = data_fixture.create_builder_page(builder=data_source.page.builder)
    data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page_dest, name="Conflict"
    )

    data_source_updated = DataSourceHandler().update_data_source(
        data_source, page=page_dest
    )

    data_source_updated.refresh_from_db()

    assert data_source_updated.page_id == page_dest.id
    assert data_source_updated.name == "Conflict 2"


@pytest.mark.django_db
def test_update_data_source_change_page_with_conflict_but_name(data_fixture):
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        name="Conflict"
    )
    page_dest = data_fixture.create_builder_page(builder=data_source.page.builder)
    data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page_dest, name="Conflict"
    )

    data_source_updated = DataSourceHandler().update_data_source(
        data_source, page=page_dest, name="Another name"
    )

    data_source_updated.refresh_from_db()

    assert data_source_updated.page_id == page_dest.id
    assert data_source_updated.name == "Another name"


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
        HttpRequest(), page, only_expose_public_formula_fields=False
    )
    result = DataSourceHandler().dispatch_data_source(data_source, dispatch_context)

    assert result == {
        "id": rows[1].id,
        "order": AnyStr(),
        fields[0].db_column: "Audi",
        fields[1].db_column: "Orange",
    }


@pytest.mark.django_db
def test_dispatch_data_sources(data_fixture):
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
        HttpRequest(), page, only_expose_public_formula_fields=False
    )
    result = DataSourceHandler().dispatch_data_sources(
        [data_source, data_source2, data_source3], dispatch_context
    )

    assert result[data_source.id] == {
        "id": rows[1].id,
        "order": AnyStr(),
        fields[0].db_column: "Audi",
        fields[1].db_column: "Orange",
    }

    assert result[data_source2.id] == {
        "id": rows[2].id,
        "order": AnyStr(),
        fields[0].db_column: "Volkswagen",
        fields[1].db_column: "White",
    }

    assert isinstance(result[data_source3.id], Exception)


@pytest.mark.django_db
def test_update_data_source_invalid_values(data_fixture):
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source()

    service_type = service_type_registry.get("local_baserow_get_row")

    data_source_updated = DataSourceHandler().update_data_source(
        data_source, service_type=service_type, nonsense="hello"
    )

    assert not hasattr(data_source_updated, "nonsense")


@pytest.mark.django_db
def test_move_data_source_end_of_page(data_fixture):
    page = data_fixture.create_builder_page()
    data_source1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )
    data_source2 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )
    data_source3 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )

    data_source_moved = DataSourceHandler().move_data_source(data_source1)

    assert DataSource.objects.filter(page=page).last().id == data_source_moved.id


@pytest.mark.django_db
def test_move_data_source_before(data_fixture):
    page = data_fixture.create_builder_page()
    data_source1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )
    data_source2 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )
    data_source3 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )

    DataSourceHandler().move_data_source(data_source3, before=data_source2)

    assert [e.id for e in DataSource.objects.filter(page=page).all()] == [
        data_source1.id,
        data_source3.id,
        data_source2.id,
    ]


@pytest.mark.django_db
def test_move_data_source_before_fails(data_fixture):
    page = data_fixture.create_builder_page()
    data_source1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page, order="2.99999999999999999998"
    )
    data_source2 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page, order="2.99999999999999999999"
    )
    data_source3 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page, order="3.0000"
    )

    with pytest.raises(CannotCalculateIntermediateOrder):
        DataSourceHandler().move_data_source(data_source3, before=data_source2)


@pytest.mark.django_db
def test_recalculate_full_orders(data_fixture):
    page = data_fixture.create_builder_page()
    data_source1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page, order="1.99999999999999999999"
    )
    data_source2 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page, order="2.00000000000000000000"
    )
    data_source3 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page, order="1.99999999999999999999"
    )
    data_source4 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page, order="2.10000000000000000000"
    )
    data_source5 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page, order="3.00000000000000000000"
    )
    data_source6 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page, order="1.00000000000000000001"
    )
    data_source7 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page, order="3.99999999999999999999"
    )
    data_source8 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page, order="4.00000000000000000001"
    )

    page2 = data_fixture.create_builder_page()

    data_sourceA = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page2, order="1.99999999999999999999"
    )
    data_sourceB = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page2, order="2.00300000000000000000"
    )

    DataSourceHandler().recalculate_full_orders(page)

    data_sources = DataSource.objects.filter(page=page)
    assert data_sources[0].id == data_source6.id
    assert data_sources[0].order == Decimal("1.00000000000000000000")

    assert data_sources[1].id == data_source1.id
    assert data_sources[1].order == Decimal("2.00000000000000000000")

    assert data_sources[2].id == data_source3.id
    assert data_sources[2].order == Decimal("3.00000000000000000000")

    assert data_sources[3].id == data_source2.id
    assert data_sources[3].order == Decimal("4.00000000000000000000")

    assert data_sources[4].id == data_source4.id
    assert data_sources[4].order == Decimal("5.00000000000000000000")

    assert data_sources[5].id == data_source5.id
    assert data_sources[5].order == Decimal("6.00000000000000000000")

    assert data_sources[6].id == data_source7.id
    assert data_sources[6].order == Decimal("7.00000000000000000000")

    assert data_sources[7].id == data_source8.id
    assert data_sources[7].order == Decimal("8.00000000000000000000")

    # Other page data_sources shouldn't be reordered
    data_sources = DataSource.objects.filter(page=page2)
    assert data_sources[0].id == data_sourceA.id
    assert data_sources[0].order == Decimal("1.99999999999999999999")

    assert data_sources[1].id == data_sourceB.id
    assert data_sources[1].order == Decimal("2.00300000000000000000")


@pytest.mark.django_db
@patch(
    "baserow.contrib.builder.data_sources.builder_dispatch_context.get_builder_used_property_names"
)
def test_dispatch_data_source_returns_formula_field_names(
    mock_get_builder_used_property_names, data_fixture, api_request_factory
):
    """
    Integration test to ensure get_builder_used_property_names() is called without
    errors.
    """

    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
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
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)

    user_source, _ = create_user_table_and_role(
        data_fixture,
        user,
        builder,
        "foo_user_role",
        integration=integration,
    )
    user_source_user = UserSourceUser(
        user_source, None, 1, "foo_username", "foo@bar.com", role="foo_user_role"
    )
    user_source_user_token = user_source_user.get_refresh_token().access_token

    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=user,
        page=page,
        integration=integration,
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
                "config": {
                    "value": f"get('data_source.{data_source.id}.field_{fields[0].id}')"
                },
            },
            {
                "name": "FieldB",
                "type": "text",
                "config": {
                    "value": f"get('data_source.{data_source.id}.field_{fields[1].id}')"
                },
            },
        ],
    )

    builder.workspace = None
    builder.save()
    data_fixture.create_builder_custom_domain(published_to=builder)

    fake_request = api_request_factory.post(
        reverse("api:builder:domains:public_dispatch_all", kwargs={"page_id": page.id}),
        {},
        HTTP_USERSOURCEAUTHORIZATION=f"JWT {user_source_user_token}",
    )
    fake_request.user = user_source_user
    dispatch_context = BuilderDispatchContext(fake_request, page)

    mock_get_builder_used_property_names.return_value = {
        "external": {data_source.service.id: [f"field_{field.id}" for field in fields]}
    }

    result = DataSourceHandler().dispatch_data_source(data_source, dispatch_context)

    assert result == {
        "has_next_page": False,
        "results": [
            {
                "id": 1,
                "order": "1.00000000000000000000",
                f"field_{fields[0].id}": "Paneer Tikka",
                f"field_{fields[1].id}": "5",
            },
            {
                "id": 2,
                "order": "2.00000000000000000000",
                f"field_{fields[0].id}": "Gobi Manchurian",
                f"field_{fields[1].id}": "8",
            },
        ],
    }
