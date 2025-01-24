from io import BytesIO
from typing import TYPE_CHECKING

from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.contrib.database.fields.exceptions import (
    InvalidRollupTargetField,
    InvalidRollupThroughField,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.formula import BaserowFormulaNumberType
from baserow.contrib.database.formula.types.exceptions import InvalidFormulaType
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.formula.parser.exceptions import FormulaFunctionTypeDoesNotExist
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig
from baserow.test_utils.helpers import AnyStr

if TYPE_CHECKING:
    from baserow.contrib.database.fields.models import (
        CountField,
        LinkRowField,
        RollupField,
    )


@pytest.mark.django_db
def test_create_rollup_through_field_with_invalid_link_row_field(
    data_fixture, api_client, django_assert_num_queries
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table2 = data_fixture.create_database_table(user=user, database=table.database)
    data_fixture.create_text_field(name="primaryfield", table=table, primary=True)
    rolled_u_field = data_fixture.create_text_field(
        name="primaryfield", table=table2, primary=True
    )
    linkrowfield = FieldHandler().create_field(
        user,
        table2,
        "link_row",
        name="linkrowfield",
        link_row_table=table2,
    )
    with pytest.raises(InvalidRollupThroughField):
        FieldHandler().create_field(
            user,
            table,
            "rollup",
            name="rollup_field",
            through_field_id=linkrowfield.id,
            target_field_id=rolled_u_field.id,
            rollup_function="sum",
        )


@pytest.mark.django_db
def test_create_rollup_through_field_with_invalid_target_field(
    data_fixture, api_client, django_assert_num_queries
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table2 = data_fixture.create_database_table(user=user, database=table.database)
    data_fixture.create_text_field(name="primaryfield", table=table, primary=True)
    rolled_up_field = data_fixture.create_text_field(name="primaryfield", primary=True)
    linkrowfield = FieldHandler().create_field(
        user,
        table,
        "link_row",
        name="linkrowfield",
        link_row_table=table2,
    )
    with pytest.raises(InvalidRollupTargetField):
        FieldHandler().create_field(
            user,
            table,
            "rollup",
            name="rollup_field",
            through_field_id=linkrowfield.id,
            target_field_id=rolled_up_field.id,
            rollup_function="sum",
        )


@pytest.mark.django_db
def test_create_rollup_through_field_with_invalid_rollup_function(
    data_fixture, api_client, django_assert_num_queries
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table2 = data_fixture.create_database_table(user=user, database=table.database)
    data_fixture.create_text_field(name="primaryfield", table=table, primary=True)
    rolled_up_field = data_fixture.create_text_field(
        name="primaryfield", table=table2, primary=True
    )
    linkrowfield = FieldHandler().create_field(
        user,
        table,
        "link_row",
        name="linkrowfield",
        link_row_table=table2,
    )
    with pytest.raises(FormulaFunctionTypeDoesNotExist):
        FieldHandler().create_field(
            user,
            table,
            "rollup",
            name="rollup_field",
            through_field_id=linkrowfield.id,
            target_field_id=rolled_up_field.id,
            rollup_function="DOES_NOT_EXIST",
        )


@pytest.mark.django_db
def test_create_rollup_through_field_with_invalid_incompatible_rollup_function(
    data_fixture, api_client, django_assert_num_queries
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table2 = data_fixture.create_database_table(user=user, database=table.database)
    data_fixture.create_text_field(name="primaryfield", table=table, primary=True)
    rolled_up_field = data_fixture.create_text_field(
        name="primaryfield",
        table=table2,
        primary=True,
    )
    linkrowfield = FieldHandler().create_field(
        user,
        table,
        "link_row",
        name="linkrowfield",
        link_row_table=table2,
    )
    with pytest.raises(InvalidFormulaType):
        FieldHandler().create_field(
            user,
            table,
            "rollup",
            name="rollup_field",
            through_field_id=linkrowfield.id,
            target_field_id=rolled_up_field.id,
            rollup_function="sum",
        )


@pytest.mark.django_db
def test_create_rollup_through_field_with_invalid_incompatible_rollup_function_via_api(
    data_fixture, api_client, django_assert_num_queries
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table2 = data_fixture.create_database_table(user=user, database=table.database)
    data_fixture.create_text_field(name="primaryfield", table=table, primary=True)
    rolled_up_field = data_fixture.create_text_field(
        name="primaryfield",
        table=table2,
        primary=True,
    )
    linkrowfield = FieldHandler().create_field(
        user,
        table,
        "link_row",
        name="linkrowfield",
        link_row_table=table2,
    )
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "rollup",
            "through_field_id": linkrowfield.id,
            "target_field_id": rolled_up_field.id,
            "rollup_function": "DOES_NOT_EXIST",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_INVALID_ROLLUP_FORMULA_FUNCTION"


@pytest.mark.django_db
def test_create_rollup_through_field_name(
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
    rolled_up_field = data_fixture.create_number_field(name="number", table=table2)
    field = FieldHandler().create_field(
        user,
        table,
        "rollup",
        name="rollup_field",
        through_field_name=linkrowfield.name,
        target_field_id=rolled_up_field.id,
        rollup_function="sum",
    )
    assert field.through_field_id == linkrowfield.id


@pytest.mark.django_db
def test_update_rollup_through_field_name(
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
    rolled_up_field = data_fixture.create_number_field(name="number", table=table2)
    field = FieldHandler().create_field(
        user,
        table,
        "rollup",
        name="rollup_field",
        through_field_id=linkrowfield.id,
        target_field_id=rolled_up_field.id,
        rollup_function="sum",
    )
    linkrowfield2 = FieldHandler().create_field(
        user,
        table,
        "link_row",
        name="linkrowfield2",
        link_row_table=table2,
    )
    field = FieldHandler().update_field(
        user,
        field,
        through_field_name=linkrowfield2.name,
    )
    assert field.through_field_id == linkrowfield2.id


@pytest.mark.django_db
def test_create_rollup_target_field_name(
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
    rolled_up_field = data_fixture.create_number_field(name="number", table=table2)
    field = FieldHandler().create_field(
        user,
        table,
        "rollup",
        name="rollup_field",
        through_field_id=linkrowfield.id,
        target_field_name=rolled_up_field.name,
        rollup_function="sum",
    )
    assert field.target_field_id == rolled_up_field.id


@pytest.mark.django_db
def test_update_rollup_target_field_name(
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
    rolled_up_field = data_fixture.create_number_field(name="number", table=table2)
    field = FieldHandler().create_field(
        user,
        table,
        "rollup",
        name="rollup_field",
        through_field_id=linkrowfield.id,
        target_field_id=rolled_up_field.id,
        rollup_function="sum",
    )
    rolled_up_field_2 = data_fixture.create_number_field(name="number2", table=table2)
    field = FieldHandler().update_field(
        user,
        field,
        target_field_name=rolled_up_field_2.name,
    )
    assert field.target_field_id == rolled_up_field_2.id


@pytest.mark.django_db
def test_can_update_rollup_field_value(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table2 = data_fixture.create_database_table(user=user, database=table.database)
    table_primary_field = data_fixture.create_text_field(
        name="p", table=table, primary=True
    )
    data_fixture.create_text_field(name="primaryfield", table=table2, primary=True)
    rolled_up_field = data_fixture.create_number_field(
        name="numberfield",
        table=table2,
    )
    link_row_field = FieldHandler().create_field(
        user,
        table,
        "link_row",
        name="linkrowfield",
        link_row_table=table2,
    )

    table2_model = table2.get_model(attribute_names=True)
    a = table2_model.objects.create(numberfield=1, primaryfield="primary a")
    b = table2_model.objects.create(numberfield=2, primaryfield="primary b")

    table_model = table.get_model(attribute_names=True)

    table_row = table_model.objects.create()
    table_row.linkrowfield.add(a.id)
    table_row.linkrowfield.add(b.id)
    table_row.save()

    rollup_field = FieldHandler().create_field(
        user,
        table,
        "rollup",
        name="rollup_field",
        through_field_id=link_row_field.id,
        target_field_id=rolled_up_field.id,
        rollup_function="sum",
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
                f"field_{link_row_field.id}": [
                    {"id": a.id, "value": "primary a", "order": AnyStr()},
                    {"id": b.id, "value": "primary b", "order": AnyStr()},
                ],
                f"field_{rollup_field.id}": "3",
                "id": table_row.id,
                "order": "1.00000000000000000000",
            }
        ],
    }
    response = api_client.patch(
        reverse(
            "api:database:rows:item",
            kwargs={"table_id": table2.id, "row_id": a.id},
        ),
        {f"field_{rolled_up_field.id}": 5},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
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
                f"field_{link_row_field.id}": [
                    {"id": a.id, "value": "primary a", "order": AnyStr()},
                    {"id": b.id, "value": "primary b", "order": AnyStr()},
                ],
                f"field_{rollup_field.id}": "7",
                "id": table_row.id,
                "order": "1.00000000000000000000",
            }
        ],
    }


@pytest.mark.django_db
def test_can_create_rollup_field_value(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table2 = data_fixture.create_database_table(user=user, database=table.database)
    table_primary_field = data_fixture.create_text_field(
        name="tableprimary", table=table, primary=True
    )
    rolled_up_field = data_fixture.create_number_field(name="number", table=table2)
    data_fixture.create_text_field(name="table2primary", table=table2, primary=True)
    link_row_field = FieldHandler().create_field(
        user,
        table,
        "link_row",
        name="linkrowfield",
        link_row_table=table2,
    )
    rollup_field = FieldHandler().create_field(
        user,
        table,
        "rollup",
        name="rollup_field",
        through_field_id=link_row_field.id,
        target_field_id=rolled_up_field.id,
        rollup_function="sum",
    )

    table2_model = table2.get_model(attribute_names=True)
    table2_row_1 = table2_model.objects.create(table2primary="row A", number=5)

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
                f"field_{rollup_field.id}": "5",
            }
        ]
    }


@pytest.mark.django_db
def test_can_create_rollup_field_with_formula_properties(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table2 = data_fixture.create_database_table(user=user, database=table.database)
    table_primary_field = data_fixture.create_text_field(
        name="tableprimary", table=table, primary=True
    )
    rolled_up_field = data_fixture.create_number_field(name="number", table=table2)
    data_fixture.create_text_field(name="table2primary", table=table2, primary=True)
    link_row_field = FieldHandler().create_field(
        user,
        table,
        "link_row",
        name="linkrowfield",
        link_row_table=table2,
    )
    rollup_field = FieldHandler().create_field(
        user,
        table,
        "rollup",
        name="rollup_field",
        through_field_id=link_row_field.id,
        target_field_id=rolled_up_field.id,
        rollup_function="sum",
        number_decimal_places=2,
    )

    table2_model = table2.get_model(attribute_names=True)
    table2_row_1 = table2_model.objects.create(table2primary="row A", number=5)

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
                f"field_{rollup_field.id}": "5.00",
            }
        ]
    }


@pytest.mark.django_db(transaction=True)
def test_import_export_tables_with_rollup_fields(
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

    rollup_field = field_handler.create_field(
        user=user,
        table=table,
        name="rollup",
        type_name="rollup",
        through_field_id=link_row_field.id,
        target_field_id=customer_age.id,
        rollup_function="sum",
    )

    config = ImportExportConfig(include_permission_data=False)
    exported_applications = core_handler.export_workspace_applications(
        database.workspace, BytesIO(), config
    )
    imported_applications, id_mapping = core_handler.import_applications_to_workspace(
        imported_workspace, exported_applications, BytesIO(), config, None
    )
    imported_database = imported_applications[0]
    imported_tables = imported_database.table_set.all()
    imported_table = imported_tables[0]
    assert imported_table.name == table.name

    imported_rollup_field = imported_table.field_set.get(
        name=rollup_field.name
    ).specific
    imported_through_field = imported_table.field_set.get(
        name=link_row_field.name
    ).specific
    imported_target_field = imported_through_field.link_row_table.field_set.get(
        name=customer_age.name
    ).specific
    assert imported_rollup_field.formula == rollup_field.formula
    assert imported_rollup_field.formula_type == BaserowFormulaNumberType.type
    assert imported_rollup_field.through_field.name == link_row_field.name
    assert imported_rollup_field.through_field_id == imported_through_field.id
    assert imported_rollup_field.target_field.name == customer_age.name
    assert imported_rollup_field.target_field_id == imported_target_field.id
    assert imported_rollup_field.rollup_function == "sum"

    imported_table_model = imported_table.get_model(attribute_names=True)
    imported_rows = imported_table_model.objects.all()
    assert imported_rows.count() == 1
    imported_row = imported_rows.first()
    assert imported_row.id == row.id
    assert imported_row.rollup == 132


@pytest.mark.django_db
def test_convert_rollup_to_text_field_via_api(data_fixture, api_client):
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
    rolled_up_field = data_fixture.create_number_field(name="number", table=table2)
    rollup_field = FieldHandler().create_field(
        user,
        table,
        "rollup",
        name="rollup_field",
        through_field_id=link_row_field.id,
        target_field_id=rolled_up_field.id,
        rollup_function="sum",
    )

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": rollup_field.id}),
        {"name": "Test 1", "type": "text"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK


# test for https://gitlab.com/baserow/baserow/-/issues/3309
@pytest.mark.parametrize(
    "field_type,field_kwargs",
    [
        (
            "rollup",
            {"rollup_function": "sum"},
        ),
        (
            "count",
            {},
        ),
    ],
)
@pytest.mark.django_db
def test_remove_dependent_count_rollup_field_through_field(
    data_fixture, api_client, field_type, field_kwargs
):
    user, token = data_fixture.create_user_and_token()
    fhandler = FieldHandler()
    table = data_fixture.create_database_table(user=user)
    referenced_table = data_fixture.create_database_table(
        user=user, database=table.database
    )

    data_fixture.create_text_field(name="primaryfield", table=table, primary=True)
    data_fixture.create_text_field(
        name="primaryfield", table=referenced_table, primary=True
    )

    linkrowfield: LinkRowField = fhandler.create_field(
        user,
        table,
        "link_row",
        name="linkrowfield",
        link_row_table=referenced_table,
        has_related_field=True,
    )

    # backref
    assert linkrowfield.link_row_related_field
    assert linkrowfield.link_row_related_field.table == referenced_table

    other_field = data_fixture.create_number_field(
        name="number", table=referenced_table
    )

    test_field: "CountField|RollupField" = fhandler.create_field(
        user,
        table,
        field_type,
        name="test_field",
        through_field_name=linkrowfield.name,
        target_field_id=other_field.id,
        **field_kwargs,
    )

    assert test_field.through_field_id == linkrowfield.id

    # before the fix, this would raise DoesNotExist for test_field.through_field
    fhandler.update_field(
        user=user, field=linkrowfield.link_row_related_field, has_related_field=False
    )

    test_field.refresh_from_db()
    assert test_field.through_field_id is None
    assert test_field.error == "references the deleted or unknown field "
