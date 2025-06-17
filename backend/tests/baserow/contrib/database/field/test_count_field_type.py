from io import BytesIO

from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.contrib.database.fields.exceptions import InvalidCountThroughField
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.formula import BaserowFormulaNumberType
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig
from baserow.test_utils.helpers import AnyStr


@pytest.mark.django_db
def test_create_count_through_field_with_invalid_linkrowfield(
    data_fixture, api_client, django_assert_num_queries
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table2 = data_fixture.create_database_table(user=user, database=table.database)
    data_fixture.create_text_field(name="primaryfield", table=table, primary=True)
    data_fixture.create_text_field(name="primaryfield", table=table2, primary=True)
    linkrowfield = FieldHandler().create_field(
        user,
        table2,
        "link_row",
        name="linkrowfield",
        link_row_table=table2,
    )
    with pytest.raises(InvalidCountThroughField):
        FieldHandler().create_field(
            user,
            table,
            "count",
            name="count_field",
            through_field_id=linkrowfield.id,
        )


@pytest.mark.django_db
def test_create_count_through_field_with_invalid_linkrowfield_via_api(
    data_fixture, api_client, django_assert_num_queries
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table2 = data_fixture.create_database_table(user=user, database=table.database)
    data_fixture.create_text_field(name="primaryfield", table=table, primary=True)
    data_fixture.create_text_field(name="primaryfield", table=table2, primary=True)
    linkrowfield = FieldHandler().create_field(
        user,
        table2,
        "link_row",
        name="linkrowfield",
        link_row_table=table2,
    )

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Test 1", "type": "count", "link_row_table_id": linkrowfield.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_INVALID_COUNT_THROUGH_FIELD"


@pytest.mark.django_db
def test_create_count_through_field_name(
    data_fixture, api_client, django_assert_num_queries
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table2 = data_fixture.create_database_table(user=user, database=table.database)
    data_fixture.create_text_field(name="primaryfield", table=table, primary=True)
    data_fixture.create_text_field(name="primaryfield", table=table2, primary=True)
    linkrowfield = FieldHandler().create_field(
        user,
        table,
        "link_row",
        name="linkrowfield",
        link_row_table=table2,
    )
    field = FieldHandler().create_field(
        user,
        table,
        "count",
        name="count_field",
        through_field_name=linkrowfield.name,
    )
    assert field.through_field_id == linkrowfield.id


@pytest.mark.django_db
def test_update_count_through_field_name(
    data_fixture, api_client, django_assert_num_queries
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table2 = data_fixture.create_database_table(user=user, database=table.database)
    data_fixture.create_text_field(name="primaryfield", table=table, primary=True)
    data_fixture.create_text_field(name="primaryfield", table=table2, primary=True)
    linkrowfield_1 = FieldHandler().create_field(
        user,
        table,
        "link_row",
        name="linkrowfield_1",
        link_row_table=table2,
    )
    linkrowfield_2 = FieldHandler().create_field(
        user,
        table,
        "link_row",
        name="linkrowfield_2",
        link_row_table=table2,
    )
    field = FieldHandler().create_field(
        user,
        table,
        "count",
        name="count_field",
        through_field_name=linkrowfield_1.name,
    )
    field = FieldHandler().update_field(
        user,
        field,
        through_field_name=linkrowfield_2.name,
    )
    assert field.through_field_id == linkrowfield_2.id


@pytest.mark.django_db
def test_can_update_count_field_value(
    data_fixture, api_client, django_assert_num_queries
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table2 = data_fixture.create_database_table(user=user, database=table.database)
    table_primary_field = data_fixture.create_text_field(
        name="p", table=table, primary=True
    )
    data_fixture.create_text_field(name="primaryfield", table=table2, primary=True)

    linkrowfield = FieldHandler().create_field(
        user,
        table,
        "link_row",
        name="linkrowfield",
        link_row_table=table2,
    )

    table2_model = table2.get_model(attribute_names=True)
    a = table2_model.objects.create(primaryfield="primary a")
    b = table2_model.objects.create(primaryfield="primary b")

    table_model = table.get_model(attribute_names=True)

    table_row = table_model.objects.create()
    table_row.linkrowfield.add(a.id)
    table_row.linkrowfield.add(b.id)
    table_row.save()

    count_field = FieldHandler().create_field(
        user,
        table,
        "count",
        name="count_field",
        through_field_id=linkrowfield.id,
    )
    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.json() == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                f"field_{table_primary_field.id}": None,
                f"field_{linkrowfield.id}": [
                    {"id": a.id, "value": "primary a", "order": AnyStr()},
                    {"id": b.id, "value": "primary b", "order": AnyStr()},
                ],
                f"field_{count_field.id}": "2",
                "id": table_row.id,
                "order": "1.00000000000000000000",
            }
        ],
    }
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_can_batch_create_count_field_value(
    data_fixture, api_client, django_assert_num_queries
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table2 = data_fixture.create_database_table(user=user, database=table.database)
    table_primary_field = data_fixture.create_text_field(
        name="tableprimary", table=table, primary=True
    )
    data_fixture.create_text_field(name="table2primary", table=table2, primary=True)
    link_row_field = FieldHandler().create_field(
        user,
        table,
        "link_row",
        name="linkrowfield",
        link_row_table=table2,
    )
    count_field = FieldHandler().create_field(
        user,
        table,
        "count",
        name="count_field",
        through_field_id=link_row_field.id,
    )

    table2_model = table2.get_model(attribute_names=True)
    table2_row_1 = table2_model.objects.create(table2primary="row A")

    response = api_client.post(
        reverse(
            "api:database:rows:batch",
            kwargs={"table_id": table.id},
        ),
        {
            "items": [
                {
                    f"field_{table_primary_field.id}": "row 1",
                    f"field_{link_row_field.id}": [table2_row_1.id],
                }
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "items": [
            {
                "id": 1,
                "order": "1.00000000000000000000",
                f"field_{table_primary_field.id}": "row 1",
                f"field_{link_row_field.id}": [
                    {"id": 1, "value": "row A", "order": AnyStr()}
                ],
                f"field_{count_field.id}": "1",
            }
        ]
    }


@pytest.mark.django_db
def test_can_batch_update_count_field_value(
    data_fixture, api_client, django_assert_num_queries
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table2 = data_fixture.create_database_table(user=user, database=table.database)
    table_primary_field = data_fixture.create_text_field(
        name="tableprimary", table=table, primary=True
    )
    data_fixture.create_text_field(name="table2primary", table=table2, primary=True)
    link_row_field = FieldHandler().create_field(
        user,
        table,
        "link_row",
        name="linkrowfield",
        link_row_table=table2,
    )
    count_field = FieldHandler().create_field(
        user,
        table,
        "count",
        name="count_field",
        through_field_id=link_row_field.id,
    )

    table1_model = table.get_model(attribute_names=True)
    table1_row_1 = table1_model.objects.create(tableprimary="row 1")

    table2_model = table2.get_model(attribute_names=True)
    table2_row_1 = table2_model.objects.create(table2primary="row A")

    response = api_client.patch(
        reverse(
            "api:database:rows:batch",
            kwargs={"table_id": table.id},
        ),
        {
            "items": [
                {"id": table1_row_1.id, f"field_{link_row_field.id}": [table2_row_1.id]}
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "items": [
            {
                "id": 1,
                "order": "1.00000000000000000000",
                f"field_{table_primary_field.id}": "row 1",
                f"field_{link_row_field.id}": [
                    {"id": 1, "value": "row A", "order": AnyStr()}
                ],
                f"field_{count_field.id}": "1",
            }
        ]
    }


@pytest.mark.django_db(transaction=True)
def test_import_export_tables_with_count_fields(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    imported_workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(
        name="Example", database=database, order=0
    )
    customers_table = data_fixture.create_database_table(
        name="Customers", database=database, order=1
    )
    customer_name = data_fixture.create_text_field(table=customers_table, primary=True)
    customer_age = data_fixture.create_number_field(table=customers_table)
    field_handler = FieldHandler()
    core_handler = CoreHandler()
    link_row_field = field_handler.create_field(
        user=user,
        table=table,
        name="Link Row",
        type_name="link_row",
        link_row_table=customers_table,
    )

    row_handler = RowHandler()
    c_row = row_handler.create_row(
        user=user,
        table=customers_table,
        values={
            f"field_{customer_name.id}": "mary",
            f"field_{customer_age.id}": 65,
        },
    )
    c_row_2 = row_handler.create_row(
        user=user,
        table=customers_table,
        values={
            f"field_{customer_name.id}": "bob",
            f"field_{customer_age.id}": 67,
        },
    )
    row = row_handler.create_row(
        user=user,
        table=table,
        values={f"field_{link_row_field.id}": [c_row.id, c_row_2.id]},
    )

    count_field = field_handler.create_field(
        user=user,
        table=table,
        name="count",
        type_name="count",
        through_field_id=link_row_field.id,
    )

    config = ImportExportConfig(include_permission_data=False)
    exported_applications = core_handler.export_workspace_applications(
        database.workspace, BytesIO(), config
    )
    imported_applications, id_mapping = core_handler.import_applications_to_workspace(
        imported_workspace,
        exported_applications,
        BytesIO(),
        config,
        None,
    )
    imported_database = imported_applications[0]
    imported_tables = imported_database.table_set.all()
    imported_table = imported_tables[0]
    assert imported_table.name == table.name

    imported_count_field = imported_table.field_set.get(name=count_field.name).specific
    imported_through_field = imported_table.field_set.get(
        name=link_row_field.name
    ).specific
    assert imported_count_field.formula == count_field.formula
    assert imported_count_field.formula_type == BaserowFormulaNumberType.type
    assert imported_count_field.through_field.name == link_row_field.name
    assert imported_count_field.through_field_id == imported_through_field.id

    imported_table_model = imported_table.get_model(attribute_names=True)
    imported_rows = imported_table_model.objects.all()
    assert imported_rows.count() == 1
    imported_row = imported_rows.first()
    assert imported_row.id == row.id
    assert imported_row.count == 2


@pytest.mark.django_db
def test_convert_count_to_text_field_via_api(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table2 = data_fixture.create_database_table(user=user, database=table.database)
    data_fixture.create_text_field(name="tableprimary", table=table, primary=True)
    data_fixture.create_text_field(name="tableprimary", table=table2, primary=True)
    link_row_field = FieldHandler().create_field(
        user,
        table,
        "link_row",
        name="linkrowfield",
        link_row_table=table2,
    )
    count_field = FieldHandler().create_field(
        user,
        table,
        "count",
        name="count_field",
        through_field_id=link_row_field.id,
    )

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": count_field.id}),
        {"name": "Test 1", "type": "text"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
