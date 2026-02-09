import inspect
import os
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import TextField
from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_204_NO_CONTENT

from baserow.contrib.database.fields.dependencies.update_collector import (
    DependencyContext,
    FieldUpdateCollector,
)
from baserow.contrib.database.fields.field_cache import FieldCache
from baserow.contrib.database.fields.field_types import FormulaFieldType
from baserow.contrib.database.fields.fields import BaserowExpressionField
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import FormulaField
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.formula import (
    BaserowFormulaInvalidType,
    BaserowFormulaNumberType,
    BaserowFormulaTextType,
)
from baserow.contrib.database.formula.ast.tree import BaserowFunctionDefinition
from baserow.contrib.database.formula.registries import formula_function_registry
from baserow.contrib.database.formula.types.exceptions import InvalidFormulaType
from baserow.contrib.database.management.commands.fill_table_rows import fill_table_rows
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.cache import generated_models_cache
from baserow.contrib.database.views.exceptions import (
    ViewFilterTypeNotAllowedForField,
    ViewSortFieldNotSupported,
)
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import SORT_ORDER_ASC, SORT_ORDER_DESC
from baserow.contrib.database.views.registries import view_filter_type_registry
from baserow.core.handler import CoreHandler
from baserow.test_utils.helpers import AnyStr


@pytest.mark.django_db
def test_creating_a_model_with_formula_field_immediately_populates_it(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    formula_field = data_fixture.create_formula_field(
        table=table, formula="'test'", formula_type="text"
    )
    formula_field_name = f"field_{formula_field.id}"
    row = RowHandler().create_row(user=user, table=table)

    assert getattr(row, formula_field_name) == "test"


@pytest.mark.django_db
def test_adding_a_formula_field_to_an_existing_table_populates_it_for_all_rows(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    existing_row = RowHandler().create_row(user, table)
    formula_field = FieldHandler().create_field(
        user, table, "formula", name="formula", formula="'test'"
    )
    formula_field_name = f"field_{formula_field.id}"
    model = table.get_model()
    row = RowHandler().create_row(user, table, {}, model=model)

    assert getattr(row, formula_field_name) == "test"
    assert getattr(model.objects.get(id=existing_row.id), formula_field_name) == "test"


@pytest.mark.django_db
def test_can_move_row_with_row_id_formula_without_loosing_value(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_formula_field(
        name="formula", table=table, formula="row_id()"
    )
    row_1, row_2 = RowHandler().force_create_rows(user, table, [{}, {}]).created_rows

    assert getattr(row_1, field.db_column) == row_1.id
    assert getattr(row_2, field.db_column) == row_2.id

    RowHandler().move_row(user, table, row_1, row_2)

    row_1.refresh_from_db()
    row_2.refresh_from_db()

    assert getattr(row_1, field.db_column) == row_1.id
    assert getattr(row_2, field.db_column) == row_2.id


@pytest.mark.django_db
def test_changing_type_of_other_field_still_results_in_working_filter(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(user, table=table)
    first_formula_field = data_fixture.create_formula_field(
        table=table, formula="'test'", formula_type="text", name="source"
    )
    formula_field_referencing_first_field = data_fixture.create_formula_field(
        table=table, formula="field('source')", formula_type="text"
    )

    data_fixture.create_view_filter(
        user=user,
        view=grid_view,
        field=formula_field_referencing_first_field,
        type="equal",
        value="t",
    )

    # Change the first formula field to be a boolean field, meaning that the view
    # filter on the referencing formula field is now and invalid and should be deleted
    FieldHandler().update_field(user, first_formula_field, formula="1")

    queryset = ViewHandler().get_queryset(user, grid_view)
    assert not queryset.exists()
    assert queryset.count() == 0


@pytest.mark.django_db
def test_can_use_complex_date_filters_on_formula_field(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(user, table=table)
    data_fixture.create_date_field(user=user, table=table, name="date_field")
    formula_field = data_fixture.create_formula_field(
        table=table, formula="field('date_field')", formula_type="date", name="formula"
    )

    data_fixture.create_view_filter(
        user=user,
        view=grid_view,
        field=formula_field,
        type="date_equals_today",
        value="Europe/London",
    )

    queryset = ViewHandler().get_queryset(user, grid_view)
    assert not queryset.exists()
    assert queryset.count() == 0


@pytest.mark.django_db
def test_can_use_complex_date_filters_on_formula_field_with_lookup(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(user, table=table)
    data_fixture.create_date_field(user=user, table=table, name="date_field")
    formula_field = data_fixture.create_formula_field(
        table=table, formula="field('date_field')", formula_type="date", name="formula"
    )

    data_fixture.create_view_filter(
        user=user,
        view=grid_view,
        field=formula_field,
        type="date_equals_years_ago",
        value="1",
    )

    table.get_model()

    queryset = ViewHandler().get_queryset(user, grid_view)
    assert not queryset.exists()
    assert queryset.count() == 0


@pytest.mark.django_db
def test_can_use_complex_contains_filters_on_formula_field(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(user, table=table)
    data_fixture.create_date_field(
        user=user, table=table, name="date_field", date_format="US"
    )
    formula_field = data_fixture.create_formula_field(
        table=table,
        formula="field('date_field')",
        formula_type="date",
        name="formula",
        date_format="US",
        date_time_format="24",
    )

    data_fixture.create_view_filter(
        user=user,
        view=grid_view,
        field=formula_field,
        type="contains",
        value="23",
    )

    queryset = ViewHandler().get_queryset(user, grid_view)
    assert not queryset.exists()
    assert queryset.count() == 0


@pytest.mark.django_db
def test_can_change_formula_type_breaking_other_fields(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    handler = FieldHandler()
    first_formula_field = handler.create_field(
        user=user, table=table, name="1", type_name="formula", formula="1+1"
    )
    second_formula_field = handler.create_field(
        user=user, table=table, type_name="formula", name="2", formula="field('1')+1"
    )
    assert list(
        second_formula_field.field_dependencies.values_list("id", flat=True)
    ) == [first_formula_field.id]
    assert list(first_formula_field.dependant_fields.values_list("id", flat=True)) == [
        second_formula_field.id
    ]
    assert (
        second_formula_field.dependencies.first().dependency.specific
        == first_formula_field
    )
    handler.update_field(
        user=user, field=first_formula_field, new_type_name="formula", formula="'a'"
    )
    second_formula_field.refresh_from_db()
    assert second_formula_field.formula_type == BaserowFormulaInvalidType.type
    assert "argument number 2" in second_formula_field.error


@pytest.mark.django_db
def test_can_still_insert_rows_with_an_invalid_but_previously_date_formula_field(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    handler = FieldHandler()
    date_field = handler.create_field(
        user=user, table=table, name="1", type_name="date"
    )
    formula_field = handler.create_field(
        user=user, table=table, type_name="formula", name="2", formula="field('1')"
    )
    handler.update_field(user=user, field=date_field, new_type_name="single_select")

    row = RowHandler().create_row(user=user, table=table)
    assert getattr(row, f"field_{formula_field.id}") is None


@pytest.mark.django_db
def test_formula_with_row_id_is_populated_after_creating_row(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    handler = FieldHandler()
    formula_field = handler.create_field(
        user=user,
        table=table,
        type_name="formula",
        name="2",
        formula="left('abc', row_id())",
    )

    row = RowHandler().create_row(user=user, table=table)
    assert getattr(row, f"field_{formula_field.id}") == "a"


@pytest.mark.django_db
def test_decimal_formula_with_row_id_is_populated_after_creating_row(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    handler = FieldHandler()
    formula_field = handler.create_field(
        user=user,
        table=table,
        type_name="formula",
        name="2",
        formula="row_id()/10 * 4",
    )

    row = RowHandler().create_row(user=user, table=table)
    assert getattr(row, f"field_{formula_field.id}") == Decimal("0.40000")


@pytest.mark.django_db
def test_can_rename_field_preserving_whitespace(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    handler = FieldHandler()
    test_field = handler.create_field(
        user=user, table=table, type_name="text", name="a"
    )
    formula_field = handler.create_field(
        user=user, table=table, type_name="formula", name="2", formula=" field('a') \n"
    )

    assert formula_field.formula == " field('a') \n"

    handler.update_field(user=user, field=test_field, name="b")

    formula_field.refresh_from_db()

    assert formula_field.formula == " field('b') \n"


@pytest.mark.django_db
def test_can_rename_field_preserving_brackets(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    handler = FieldHandler()
    test_field = handler.create_field(
        user=user, table=table, type_name="number", name="a"
    )
    formula_field = handler.create_field(
        user=user,
        table=table,
        type_name="formula",
        name="2",
        formula="field('a') / (field('a') + field('a'))",
    )

    assert formula_field.formula == "field('a') / (field('a') + field('a'))"

    handler.update_field(user=user, field=test_field, name="b")

    formula_field.refresh_from_db()

    assert formula_field.formula == "field('b') / (field('b') + field('b'))"


@pytest.mark.django_db
def test_can_update_lookup_field_value(
    data_fixture, api_client, django_assert_num_queries
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table2 = data_fixture.create_database_table(user=user, database=table.database)
    table_primary_field = data_fixture.create_text_field(
        name="p", table=table, primary=True
    )
    data_fixture.create_text_field(name="primaryfield", table=table2, primary=True)
    looked_up_field = data_fixture.create_date_field(
        name="lookupfield",
        table=table2,
        date_include_time=False,
        date_format="US",
    )

    linkrowfield = FieldHandler().create_field(
        user,
        table,
        "link_row",
        name="linkrowfield",
        link_row_table=table2,
    )

    table2_model = table2.get_model(attribute_names=True)
    a = table2_model.objects.create(lookupfield="2021-02-01", primaryfield="primary a")
    b = table2_model.objects.create(lookupfield="2022-02-03", primaryfield="primary b")

    table_model = table.get_model(attribute_names=True)

    table_row = table_model.objects.create()
    table_row.linkrowfield.add(a.id)
    table_row.linkrowfield.add(b.id)
    table_row.save()

    formulafield = FieldHandler().create_field(
        user,
        table,
        "formula",
        name="formulafield",
        formula=f"IF(datetime_format(lookup('{linkrowfield.name}',"
        f"'{looked_up_field.name}'), "
        f"'YYYY')='2021', 'yes', 'no')",
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
                f"field_{formulafield.id}": [
                    {"value": "yes", "id": a.id},
                    {"value": "no", "id": b.id},
                ],
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
        {f"field_{looked_up_field.id}": "2000-02-01"},
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
                f"field_{linkrowfield.id}": [
                    {"id": a.id, "value": "primary a", "order": AnyStr()},
                    {"id": b.id, "value": "primary b", "order": AnyStr()},
                ],
                f"field_{formulafield.id}": [
                    {"value": "no", "id": a.id},
                    {"value": "no", "id": b.id},
                ],
                "id": table_row.id,
                "order": "1.00000000000000000000",
            }
        ],
    }


@pytest.mark.django_db
def test_nested_lookup_with_formula(
    data_fixture, api_client, django_assert_num_queries
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table2 = data_fixture.create_database_table(user=user, database=table.database)
    table3 = data_fixture.create_database_table(user=user, database=table.database)
    table_primary_field = data_fixture.create_text_field(
        name="p", table=table, primary=True
    )
    data_fixture.create_text_field(name="p", table=table3, primary=True)
    data_fixture.create_text_field(name="p", table=table2, primary=True)
    data_fixture.create_text_field(name="lookupfield", table=table2)
    linkrowfield = FieldHandler().create_field(
        user,
        table,
        "link_row",
        name="table_linkrowfield",
        link_row_table=table2,
    )
    linkrowfield2 = FieldHandler().create_field(
        user,
        table2,
        "link_row",
        name="table2_linkrowfield",
        link_row_table=table3,
    )
    table3_model = table3.get_model(attribute_names=True)
    table3_a = table3_model.objects.create(p="table3 a")
    table3_model.objects.create(p="table3 b")
    table3_c = table3_model.objects.create(p="table3 c")
    table3_d = table3_model.objects.create(p="table3 d")
    table2_model = table2.get_model(attribute_names=True)
    table2_1 = table2_model.objects.create(lookupfield="lookup 1", p="primary 1")
    table2_1.table2linkrowfield.add(table3_a.id)
    table2_1.save()
    table2_2 = table2_model.objects.create(lookupfield="lookup 2", p="primary 2")
    table2_3 = table2_model.objects.create(lookupfield="lookup 3", p="primary 3")
    table2_3.table2linkrowfield.add(table3_c.id)
    table2_3.table2linkrowfield.add(table3_d.id)
    table2_3.save()
    table_model = table.get_model(attribute_names=True)
    table1_x = table_model.objects.create(p="table1 x")
    table1_x.tablelinkrowfield.add(table2_1.id)
    table1_x.tablelinkrowfield.add(table2_2.id)
    table1_x.save()
    table1_y = table_model.objects.create(p="table1 y")
    table1_y.tablelinkrowfield.add(table2_3.id)
    table1_y.save()
    # with django_assert_num_queries(1):
    lookup_field = FieldHandler().create_field(
        user,
        table,
        type_name="formula",
        name="formula",
        formula=f"lookup('{linkrowfield.name}','{linkrowfield2.name}')",
    )
    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.json() == {
        "count": 2,
        "next": None,
        "previous": None,
        "results": [
            {
                f"field_{table_primary_field.id}": table1_x.p,
                f"field_{linkrowfield.id}": [
                    {"id": table2_1.id, "value": table2_1.p, "order": AnyStr()},
                    {"id": table2_2.id, "value": table2_2.p, "order": AnyStr()},
                ],
                f"field_{lookup_field.id}": [
                    {
                        "value": table3_a.p,
                        "ids": {
                            f"database_table_{table2.id}": table2_1.id,
                            f"database_table_{table3.id}": table3_a.id,
                        },
                    },
                ],
                "id": table1_x.id,
                "order": "1.00000000000000000000",
            },
            {
                f"field_{table_primary_field.id}": table1_y.p,
                f"field_{linkrowfield.id}": [
                    {"id": table2_3.id, "value": table2_3.p, "order": AnyStr()}
                ],
                f"field_{lookup_field.id}": [
                    {
                        "value": table3_c.p,
                        "ids": {
                            f"database_table_{table2.id}": table2_3.id,
                            f"database_table_{table3.id}": table3_c.id,
                        },
                    },
                    {
                        "value": table3_d.p,
                        "ids": {
                            f"database_table_{table2.id}": table2_3.id,
                            f"database_table_{table3.id}": table3_d.id,
                        },
                    },
                ],
                "id": table1_y.id,
                "order": "1.00000000000000000000",
            },
        ],
    }


@pytest.mark.django_db
def test_can_delete_lookup_field_value(
    data_fixture, api_client, django_assert_num_queries
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table2 = data_fixture.create_database_table(user=user, database=table.database)
    table_primary_field = data_fixture.create_text_field(
        name="p", table=table, primary=True
    )
    data_fixture.create_text_field(name="primaryfield", table=table2, primary=True)
    looked_up_field = data_fixture.create_date_field(
        name="lookupfield",
        table=table2,
        date_include_time=False,
        date_format="US",
    )

    linkrowfield = FieldHandler().create_field(
        user,
        table,
        "link_row",
        name="linkrowfield",
        link_row_table=table2,
    )

    table2_model = table2.get_model(attribute_names=True)
    a = table2_model.objects.create(lookupfield="2021-02-01", primaryfield="primary a")
    b = table2_model.objects.create(lookupfield="2022-02-03", primaryfield="primary b")

    table_model = table.get_model(attribute_names=True)

    table_row = table_model.objects.create(p="table row 1")
    table_row.linkrowfield.add(a.id)
    table_row.linkrowfield.add(b.id)
    table_row.save()

    formulafield = FieldHandler().create_field(
        user,
        table,
        "formula",
        name="formulafield",
        formula=f"IF(datetime_format(lookup('{linkrowfield.name}',"
        f"'{looked_up_field.name}'), "
        f"'YYYY')='2021', 'yes', 'no')",
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
                f"field_{table_primary_field.id}": "table row 1",
                f"field_{linkrowfield.id}": [
                    {"id": a.id, "value": "primary a", "order": AnyStr()},
                    {"id": b.id, "value": "primary b", "order": AnyStr()},
                ],
                f"field_{formulafield.id}": [
                    {"value": "yes", "id": a.id},
                    {"value": "no", "id": b.id},
                ],
                "id": table_row.id,
                "order": "1.00000000000000000000",
            }
        ],
    }
    response = api_client.delete(
        reverse(
            "api:database:rows:item",
            kwargs={"table_id": table2.id, "row_id": a.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT
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
                f"field_{table_primary_field.id}": "table row 1",
                f"field_{linkrowfield.id}": [
                    {"id": b.id, "value": "primary b", "order": AnyStr()},
                ],
                f"field_{formulafield.id}": [
                    {"value": "no", "id": b.id},
                ],
                "id": table_row.id,
                "order": "1.00000000000000000000",
            }
        ],
    }


@pytest.mark.django_db
def test_can_delete_double_link_lookup_field_value(
    data_fixture, api_client, django_assert_num_queries
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    table2 = data_fixture.create_database_table(user=user, database=table.database)
    table3 = data_fixture.create_database_table(user=user, database=table.database)
    table_primary_field = data_fixture.create_text_field(
        name="p", table=table, primary=True
    )
    data_fixture.create_text_field(name="primaryfield", table=table2, primary=True)
    data_fixture.create_text_field(name="primaryfield", table=table3, primary=True)
    table2_linkrowfield = FieldHandler().create_field(
        user,
        table2,
        "link_row",
        name="linkrowfield",
        link_row_table=table3,
    )
    table3_model = table3.get_model(attribute_names=True)
    table3_1 = table3_model.objects.create(primaryfield="table 3 row 1")
    table3_2 = table3_model.objects.create(primaryfield="table 3 row 2")

    linkrowfield = FieldHandler().create_field(
        user,
        table,
        "link_row",
        name="linkrowfield",
        link_row_table=table2,
    )

    table2_model = table2.get_model(attribute_names=True)
    table2_a = table2_model.objects.create(primaryfield="primary a")
    table2_a.linkrowfield.add(table3_1.id)
    table2_a.save()
    table2_b = table2_model.objects.create(primaryfield="primary b")
    table2_b.linkrowfield.add(table3_2.id)
    table2_b.save()

    table_model = table.get_model(attribute_names=True)

    table_row = table_model.objects.create(p="table row 1")
    table_row.linkrowfield.add(table2_a.id)
    table_row.linkrowfield.add(table2_b.id)
    table_row.save()

    formulafield = FieldHandler().create_field(
        user,
        table,
        "formula",
        name="formulafield",
        formula=f"lookup('{linkrowfield.name}','{table2_linkrowfield.name}')",
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
                f"field_{table_primary_field.id}": "table row 1",
                f"field_{linkrowfield.id}": [
                    {"id": table2_a.id, "value": "primary a", "order": AnyStr()},
                    {"id": table2_b.id, "value": "primary b", "order": AnyStr()},
                ],
                f"field_{formulafield.id}": [
                    {
                        "value": table3_1.primaryfield,
                        "ids": {
                            f"database_table_{table2.id}": table2_a.id,
                            f"database_table_{table3.id}": table3_1.id,
                        },
                    },
                    {
                        "value": table3_2.primaryfield,
                        "ids": {
                            f"database_table_{table2.id}": table2_b.id,
                            f"database_table_{table3.id}": table3_2.id,
                        },
                    },
                ],
                "id": table_row.id,
                "order": "1.00000000000000000000",
            }
        ],
    }
    response = api_client.delete(
        reverse(
            "api:database:rows:item",
            kwargs={"table_id": table2.id, "row_id": table2_a.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT
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
                f"field_{table_primary_field.id}": "table row 1",
                f"field_{linkrowfield.id}": [
                    {"id": table2_b.id, "value": "primary b", "order": AnyStr()},
                ],
                f"field_{formulafield.id}": [
                    {
                        "value": table3_2.primaryfield,
                        "ids": {
                            f"database_table_{table2.id}": table2_b.id,
                            f"database_table_{table3.id}": table3_2.id,
                        },
                    },
                ],
                "id": table_row.id,
                "order": "1.00000000000000000000",
            }
        ],
    }

    response = api_client.delete(
        reverse(
            "api:database:rows:item",
            kwargs={"table_id": table3.id, "row_id": table3_2.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT
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
                f"field_{table_primary_field.id}": "table row 1",
                f"field_{linkrowfield.id}": [
                    {"id": table2_b.id, "value": "primary b", "order": AnyStr()},
                ],
                f"field_{formulafield.id}": [],
                "id": table_row.id,
                "order": "1.00000000000000000000",
            }
        ],
    }


@pytest.mark.django_db
def test_all_functions_are_registered():
    def get_all_subclasses(cls):
        all_subclasses = []

        for subclass in cls.__subclasses__():
            if not inspect.isabstract(subclass):
                all_subclasses.append(subclass)
            all_subclasses.extend(get_all_subclasses(subclass))

        return all_subclasses

    funcs = formula_function_registry.get_all()
    names = [f.type for f in funcs]
    assert len(names) == len(get_all_subclasses(BaserowFunctionDefinition))


@pytest.mark.django_db
def test_row_dependency_update_functions_do_one_row_updates_for_same_table(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    handler = FieldHandler()
    handler.create_field(user=user, table=table, type_name="text", name="a")
    # noinspection PyTypeChecker
    formula_field: FormulaField = handler.create_field(
        user=user,
        table=table,
        type_name="formula",
        name="formula",
        formula="field('a')",
    )
    table_model = table.get_model()
    row = RowHandler().create_row(user, table, model=table_model)
    formula_field_type = FormulaFieldType()
    update_collector = FieldUpdateCollector(table)
    field_cache = FieldCache()
    field_cache.cache_model(table_model)

    dependency_context = DependencyContext(depth=0)
    formula_field_type.row_of_dependency_updated(
        formula_field, row, update_collector, field_cache, None, dependency_context
    )
    formula_field_type.row_of_dependency_updated(
        formula_field, row, update_collector, field_cache, [], dependency_context
    )
    formula_field_type.row_of_dependency_created(
        formula_field, row, update_collector, field_cache, None, dependency_context
    )
    formula_field_type.row_of_dependency_created(
        formula_field, row, update_collector, field_cache, [], dependency_context
    )
    formula_field_type.row_of_dependency_deleted(
        formula_field, row, update_collector, field_cache, None, dependency_context
    )
    formula_field_type.row_of_dependency_deleted(
        formula_field, row, update_collector, field_cache, [], dependency_context
    )
    # Does one update to update the last_system_or_user_row_update_on column
    with django_assert_num_queries(1):
        update_collector.apply_updates_and_get_updated_fields(field_cache)


@pytest.mark.django_db
def test_recalculated_internal_type_with_incorrect_syntax_formula_sets_to_invalid(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    handler = FieldHandler()
    handler.create_field(user=user, table=table, type_name="text", name="a")
    formula_field = handler.create_field(
        user=user,
        table=table,
        type_name="formula",
        name="formula",
        formula="field('a')",
    )
    formula_field.formula = "invalid"
    formula_field.save()
    assert formula_field.formula_type == BaserowFormulaInvalidType.type
    assert "Invalid syntax" in formula_field.error


@pytest.mark.django_db
def test_accessing_cached_internal_formula_second_time_does_no_queries(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    handler = FieldHandler()
    a_field = handler.create_field(user=user, table=table, type_name="text", name="a")
    formula_field = handler.create_field(
        user=user,
        table=table,
        type_name="formula",
        name="formula",
        formula="field('a')",
    )
    with django_assert_num_queries(0):
        assert str(formula_field.cached_untyped_expression) == formula_field.formula
        assert (
            str(formula_field.cached_typed_internal_expression)
            == f"error_to_null(field('{a_field.db_column}'))"
        )
        assert formula_field.cached_formula_type.type == BaserowFormulaTextType.type


@pytest.mark.django_db
def test_saving_after_properties_have_been_cached_does_recalculation(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    handler = FieldHandler()
    a_field = handler.create_field(user=user, table=table, type_name="text", name="a")
    formula_field = handler.create_field(
        user=user,
        table=table,
        type_name="formula",
        name="formula",
        formula="field('a')",
    )
    assert str(formula_field.cached_untyped_expression) == formula_field.formula
    assert (
        str(formula_field.cached_typed_internal_expression)
        == f"error_to_null(field('{a_field.db_column}'))"
    )
    assert formula_field.cached_formula_type.type == BaserowFormulaTextType.type

    formula_field.formula = "1"
    formula_field.save()

    assert str(formula_field.cached_untyped_expression) == "1"
    assert str(formula_field.cached_typed_internal_expression) == "error_to_nan(1)"
    assert formula_field.cached_formula_type.type == BaserowFormulaNumberType.type


@pytest.mark.django_db
def test_renaming_dependency_maintains_dependency_link(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    handler = FieldHandler()
    a_field = handler.create_field(user=user, table=table, type_name="text", name="a")
    formula_field = handler.create_field(
        user=user,
        table=table,
        type_name="formula",
        name="formula",
        formula="field('a')",
    )
    starting_dep = formula_field.dependencies.get()
    assert formula_field.field_dependencies.get().id == a_field.id
    assert starting_dep.broken_reference_field_name is None
    assert starting_dep.dependency_id == a_field.id
    handler.update_field(user, a_field, name="other")

    formula_field.refresh_from_db()
    assert formula_field.dependencies.get().id == starting_dep.id
    assert formula_field.field_dependencies.get().id == a_field.id
    assert formula_field.formula == "field('other')"


@pytest.mark.django_db
def test_can_insert_and_update_rows_with_formula_referencing_single_select(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    handler = FieldHandler()
    option_field = data_fixture.create_single_select_field(
        table=table, name="option_field", order=1
    )
    option_a = data_fixture.create_select_option(
        field=option_field, value="A", color="blue"
    )
    option_b = data_fixture.create_select_option(
        field=option_field, value="B", color="red"
    )
    formula_field = handler.create_field(
        user=user,
        table=table,
        type_name="formula",
        name="2",
        formula="field('option_field')",
    )

    row = RowHandler().create_row(
        user=user, table=table, values={f"field_{option_field.id}": option_a.id}
    )
    row.refresh_from_db()
    result = getattr(row, f"field_{formula_field.id}")
    assert result == {
        "id": option_a.id,
        "color": option_a.color,
        "value": option_a.value,
    }

    row = RowHandler().update_row_by_id(
        user=user,
        table=table,
        row_id=row.id,
        values={f"field_{option_field.id}": option_b.id},
    )
    row.refresh_from_db()
    result = getattr(row, f"field_{formula_field.id}")
    assert result == {
        "id": option_b.id,
        "color": option_b.color,
        "value": option_b.value,
    }

    row = RowHandler().create_row(user=user, table=table, values={})
    row.refresh_from_db()
    result = getattr(row, f"field_{formula_field.id}")
    assert result is None


@pytest.mark.django_db
def test_cannot_create_view_filter_or_sort_on_invalid_field(data_fixture):
    user = data_fixture.create_user()
    table, other_table, link = data_fixture.create_two_linked_tables(user=user)
    grid_view = data_fixture.create_grid_view(user, table=table)
    first_formula_field = FieldHandler().create_field(
        user, table, "formula", formula="1", name="source"
    )
    broken_formula_field = FieldHandler().create_field(
        user, table, "formula", formula="field('source')", name="a"
    )
    FieldHandler().delete_field(user, first_formula_field)

    option_field = data_fixture.create_single_select_field(
        table=table, name="option_field", order=1
    )
    data_fixture.create_select_option(field=option_field, value="A", color="blue")
    data_fixture.create_select_option(field=option_field, value="B", color="red")
    broken_formula_field = FormulaField.objects.get(id=broken_formula_field.id)
    assert broken_formula_field.formula_type == "invalid"

    fields_which_cant_yet_be_sorted_or_filtered = [
        broken_formula_field,
    ]
    for field in fields_which_cant_yet_be_sorted_or_filtered:
        for view_filter_type in view_filter_type_registry.get_all():
            with pytest.raises(ViewFilterTypeNotAllowedForField):
                ViewHandler().create_filter(
                    user,
                    grid_view,
                    field,
                    view_filter_type.type,
                    "",
                )

    for field in fields_which_cant_yet_be_sorted_or_filtered:
        with pytest.raises(ViewSortFieldNotSupported):
            ViewHandler().create_sort(user, grid_view, field, SORT_ORDER_ASC)

        with pytest.raises(ViewSortFieldNotSupported):
            ViewHandler().create_sort(user, grid_view, field, SORT_ORDER_DESC)


@pytest.mark.django_db
def test_can_cache_and_uncache_formula_model_field(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    handler = FieldHandler()
    formula_field = handler.create_field(
        user=user,
        table=table,
        type_name="formula",
        name="2",
        formula="'a'",
    )
    formula_field_type = field_type_registry.get_by_model(formula_field)
    formula_model_field = formula_field_type.get_model_field(formula_field)
    generated_models_cache.set("test_formula_key", formula_model_field)
    uncached = generated_models_cache.get("test_formula_key")
    assert uncached == formula_model_field
    assert isinstance(uncached, BaserowExpressionField)
    assert uncached.__class__ == TextField
    assert str(uncached.expression) == str(formula_model_field.expression)


@pytest.mark.django_db
def test_inserting_a_row_with_lookup_field_immediately_populates_it_with_empty_list(
    data_fixture,
):
    user = data_fixture.create_user()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)

    primary_a_field = table_a.field_set.get(primary=True)
    primary_b_field = table_b.field_set.get(primary=True)
    target_field = data_fixture.create_text_field(name="target", table=table_b)
    row_1, row_2 = (
        RowHandler()
        .create_rows(
            user,
            table_b,
            rows_values=[
                {primary_b_field.db_column: "1", target_field.db_column: "target 1"},
                {primary_b_field.db_column: "2", target_field.db_column: "target 2"},
            ],
        )
        .created_rows
    )
    RowHandler().create_rows(
        user,
        table_a,
        rows_values=[
            {
                primary_a_field.db_column: "a",
                link_field.db_column: [row_1.id, row_2.id],
            }
        ],
    )

    lookup = FieldHandler().create_field(
        user,
        table_a,
        "lookup",
        name="lookup",
        through_field_name="link",
        target_field_name="target",
    )
    inserted_row = RowHandler().create_row(user, table_a)
    default_empty_value_for_lookup = getattr(inserted_row, f"field_{lookup.id}")
    assert default_empty_value_for_lookup is not None
    assert default_empty_value_for_lookup == []


@pytest.mark.django_db
def test_multiple_formula_fields_with_different_django_lookups_being_used_to_filter(
    data_fixture, api_client, django_assert_num_queries
):
    user, token = data_fixture.create_user_and_token()

    table = data_fixture.create_database_table(user=user)

    grid_view = data_fixture.create_grid_view(user=user, table=table)
    option_field = data_fixture.create_single_select_field(user=user, table=table)

    formula_field_ref_link_field = FieldHandler().create_field(
        user=user, table=table, name="a", type_name="formula", formula="1"
    )
    formula_referencing_single_select = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="formula",
        formula=f"field('{option_field.name}')",
        name="single_select_formula",
    )

    data_fixture.create_view_filter(
        user=user,
        view=grid_view,
        field=formula_field_ref_link_field,
        type="empty",
    )

    response = api_client.get(
        reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_cant_create_primary_lookup_that_looksup_itself(data_fixture):
    user = data_fixture.create_user()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)

    with pytest.raises(
        InvalidFormulaType,
        match="references itself via a link field causing a circular dependency",
    ):
        FieldHandler().update_field(
            user,
            table_a.field_set.get(primary=True).specific,
            new_type_name="formula",
            name="formulafield",
            formula=f"lookup('{link_field.name}', '{link_field.link_row_related_field.name}')",
        )


@pytest.mark.django_db(transaction=True)
def test_converting_link_row_field_with_formula_dependency(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)

    table_b_primary_field = table_b.field_set.get(primary=True)
    table_a_primary_field = table_a.field_set.get(primary=True)
    lookup_of_table_b_pk = FieldHandler().create_field(
        user,
        table=table_a,
        type_name="formula",
        name="broken",
        formula=f"lookup('{link_field.name}','{table_b_primary_field.name}')",
    )
    # Change the link field to a text field, this should break the lookup formula
    with transaction.atomic():
        FieldHandler().update_field(user, link_field, new_type_name="text")

    lookup_of_table_b_pk.refresh_from_db()
    assert lookup_of_table_b_pk.formula_type == "invalid"
    assert (
        lookup_of_table_b_pk.error
        == "first lookup function argument must be a link row field"
    )


@pytest.mark.django_db(transaction=True)
def test_converted_reversed_link_row_field_with_formula_dependency(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)

    table_b_primary_field = table_b.field_set.get(primary=True)
    table_a_primary_field = table_a.field_set.get(primary=True)
    related_link_row_field = link_field.link_row_related_field
    lookup_of_table_b_pk = FieldHandler().create_field(
        user,
        table=table_a,
        type_name="formula",
        name="broken",
        formula=f"lookup('{link_field.name}','{table_b_primary_field.name}')",
    )
    # Change the link field to a text field, this should break the lookup formula
    with transaction.atomic():
        FieldHandler().update_field(user, related_link_row_field, new_type_name="text")

    lookup_of_table_b_pk.refresh_from_db()
    assert lookup_of_table_b_pk.formula_type == "invalid"
    assert lookup_of_table_b_pk.error == "references the deleted or unknown field link"


def can_query_grid_view_for(api_client, grid_view, token):
    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json["results"]) == 10


@pytest.mark.django_db(transaction=True)
def test_every_formula_sub_type_can_be_a_primary_field(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)
    grid_view_table_a = data_fixture.create_grid_view(user, table=table_a)
    grid_view_table_b = data_fixture.create_grid_view(user, table=table_b)

    table_b_primary_field = table_b.field_set.get(primary=True)
    table_a_primary_field = table_a.field_set.get(primary=True).specific
    related_link_row_field = link_field.link_row_related_field

    data_fixture.create_email_field(table=table_a, name="email")
    option_field_table_a = data_fixture.create_single_select_field(
        table=table_a, name="single_select"
    )
    data_fixture.create_select_option(
        field=option_field_table_a, value="A", color="blue"
    )
    data_fixture.create_select_option(
        field=option_field_table_a, value="B", color="red"
    )

    data_fixture.create_text_field(table=table_b, name="text")
    data_fixture.create_number_field(table=table_b, name="int", number_decimal_places=0)
    data_fixture.create_boolean_field(table=table_b, name="bool")
    data_fixture.create_number_field(
        table=table_b, name="decimal", number_decimal_places=10
    )
    data_fixture.create_formula_field(
        table=table_b, name="date_interval", formula='date_interval("1 day")'
    )
    data_fixture.create_date_field(table=table_b, name="date")
    option_field_table_b = data_fixture.create_single_select_field(
        table=table_b, name="single_select"
    )
    data_fixture.create_select_option(
        field=option_field_table_b, value="A", color="blue"
    )
    data_fixture.create_select_option(
        field=option_field_table_b, value="B", color="red"
    )
    data_fixture.create_email_field(table=table_b, name="email")

    fill_table_rows(10, table_a)
    fill_table_rows(10, table_b)

    every_formula_type = [
        "CONCAT('test ', UPPER('formula'))",
        "1",
        "true",
        "100/3",
        "date_interval('1 day')",
        "todate('20200101', 'YYYYMMDD')",
        "field('single_select')",
        "field('email')",
        "1/0",
        f"lookup('{link_field.name}', 'text')",
        f"lookup('{link_field.name}', 'int')",
        f"lookup('{link_field.name}', 'bool')",
        f"lookup('{link_field.name}', 'decimal')",
        f"lookup('{link_field.name}', 'date_interval')",
        f"lookup('{link_field.name}', 'date')",
        f"lookup('{link_field.name}', 'single_select')",
        f"lookup('{link_field.name}', 'email')",
    ]
    for f in every_formula_type:
        primary_formula = FieldHandler().update_field(
            user,
            table_a_primary_field,
            new_type_name="formula",
            name="primary formula",
            formula=f,
        )
        assert primary_formula.error is None
        can_query_grid_view_for(api_client, grid_view_table_a, token)
        can_query_grid_view_for(api_client, grid_view_table_b, token)


@pytest.mark.django_db
def test_can_have_nested_date_formulas(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_date_field(table=table, name="jaar_van")

    FieldHandler().create_field(
        user,
        table,
        "formula",
        name="datum",
        formula="todate(concat(totext(year(field('jaar_van'))),'-01-01'),'YYYY-MM-DD')",
    )
    FieldHandler().create_field(
        user,
        table,
        "formula",
        name="failured",
        formula="date_diff('day', field('jaar_van'), field('datum')) + 1",
    )


@pytest.mark.django_db
def test_formula_field_adjacent_row(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    grid_view = data_fixture.create_grid_view(user=user, table=table, name="Test")
    text_field = data_fixture.create_text_field(table=table)
    formula_field = data_fixture.create_formula_field(
        table=table,
        formula=f"field('{text_field.name}')",
        formula_type="text",
    )

    data_fixture.create_view_sort(view=grid_view, field=formula_field, order="DESC")

    table_model = table.get_model()
    handler = RowHandler()
    [row_a, row_b, row_c] = handler.create_rows(
        user=user,
        table=table,
        rows_values=[
            {
                f"field_{text_field.id}": "A",
            },
            {
                f"field_{text_field.id}": "B",
            },
            {
                f"field_{text_field.id}": "C",
            },
        ],
    ).created_rows

    previous_row = handler.get_adjacent_row(
        table_model, row_b.id, previous=True, view=grid_view
    )
    next_row = handler.get_adjacent_row(table_model, row_b.id, view=grid_view)

    assert previous_row.id == row_c.id
    assert next_row.id == row_a.id


@pytest.mark.django_db
def test_updating_formula_field_doesnt_reset_all_fields(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_date_field(table=table, name="jaar_van")

    f = FieldHandler().create_field(
        user,
        table,
        "formula",
        name="datum",
        formula="todate(concat(totext(year(field('jaar_van'))),'-01-01'),'YYYY-MM-DD')",
    )
    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": f.id}),
        {
            "type": "formula",
            "formula": "todate('1000-01-01','YYYY-MM-DD')",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    expected = {
        "array_formula_type": None,
        "date_force_timezone": None,
        "date_format": "ISO",
        "date_include_time": False,
        "date_show_tzinfo": False,
        "date_time_format": "24",
        "error": None,
        "formula": "todate('1000-01-01','YYYY-MM-DD')",
        "formula_type": "date",
        "nullable": True,
        "number_decimal_places": None,
    }
    actual = {key: value for key, value in response.json().items() if key in expected}
    assert actual == expected
    f.refresh_from_db()
    assert f.date_format is not None


@pytest.mark.django_db
def test_user_can_change_date_force_timezone_on_formula(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_date_field(table=table, name="jaar_van")

    f = FieldHandler().create_field(
        user,
        table,
        "formula",
        name="datum",
        formula="todate(concat(totext(year(field('jaar_van'))),'-01-01'),'YYYY-MM-DD')",
    )
    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": f.id}),
        {
            "type": "formula",
            "formula": "todate('1000-01-01','YYYY-MM-DD')",
            "date_force_timezone": "GMT",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    expected = {
        "date_force_timezone": "GMT",
    }
    actual = {key: value for key, value in response.json().items() if key in expected}
    assert actual == expected

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": f.id}),
        {
            "type": "formula",
            "formula": "todate('1000-01-01','YYYY-MM-DD')",
            "date_force_timezone": None,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    expected = {
        "date_force_timezone": None,
    }
    actual = {key: value for key, value in response.json().items() if key in expected}
    assert actual == expected


@pytest.mark.django_db
@pytest.mark.field_formula
@pytest.mark.parametrize(
    "instance1,instance2,is_compatible",
    [
        (
            FormulaField(formula_type="date", array_formula_type=None),
            FormulaField(formula_type="date", array_formula_type=None),
            True,
        ),
        (
            FormulaField(formula_type="array", array_formula_type="number"),
            FormulaField(formula_type="array", array_formula_type="number"),
            True,
        ),
        (
            FormulaField(formula_type="date", array_formula_type=None),
            FormulaField(formula_type="number", array_formula_type=None),
            False,
        ),
        (
            FormulaField(formula_type="array", array_formula_type="number"),
            FormulaField(formula_type="array", array_formula_type="text"),
            False,
        ),
    ],
)
def test_has_compatible_model_fields(instance1, instance2, is_compatible):
    FormulaFieldType().has_compatible_model_fields(
        instance1, instance2
    ) is is_compatible


def _create_arr_sort_fixture(
    data_fixture, create_primary_field, formula_type, distinct_values, unsorted_rows
):
    row_handler = RowHandler()
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="db")

    # related table
    related_table = data_fixture.create_database_table(
        name="Related table", database=database
    )
    related_primary_field = create_primary_field(related_table)
    related_table_model = related_table.get_model()

    related_table_rows = {}
    for dv in distinct_values:
        related_table_rows[dv] = related_table_model.objects.create(
            **{f"field_{related_primary_field.id}": dv}
        )

    # main table
    table = data_fixture.create_database_table(name="Main table", database=database)
    data_fixture.create_text_field(
        table=table, order=1, primary=True, name="Primary text"
    )
    link_row_field = data_fixture.create_link_row_field(
        name="link", table=table, link_row_table=related_table
    )
    formula_field = data_fixture.create_formula_field(
        table=table,
        name="formula_lookup",
        formula=f"lookup('{link_row_field.name}', '{related_primary_field.name}')",
        formula_type=formula_type,
    )
    grid_view = data_fixture.create_grid_view(table=table)

    for index, field_values in enumerate(unsorted_rows):
        for index2, value in enumerate(field_values):
            unsorted_rows[index][index2] = related_table_rows[value].id

    for row_list in unsorted_rows:
        row_handler.create_row(
            user=user, table=table, values={f"field_{link_row_field.id}": row_list}
        )

    return table.get_model(), formula_field, grid_view


@pytest.mark.django_db
def test_formula_field_type_lookup_sorting_array_text(
    data_fixture,
):
    def create_primary_field(table):
        return data_fixture.create_text_field(
            table=table, order=1, primary=True, name="Primary text"
        )

    distinct_values = ["a", "b", "aa", "bb", "aaa", ""]
    formula_type = "text"
    unsorted_rows = [
        ["b", "a"],
        ["a"],
        ["a", "b"],
        [],
        ["b", "aaa"],
        ["b"],
        [""],
        ["aa"],
    ]
    model, formula_field, grid_view = _create_arr_sort_fixture(
        data_fixture, create_primary_field, formula_type, distinct_values, unsorted_rows
    )

    expected = [
        ["b", "aaa"],
        ["b"],
        ["aa"],
        ["a", "b"],
        ["a", "b"],
        ["a"],
        [""],
        None,
    ]

    view_handler = ViewHandler()
    sort = data_fixture.create_view_sort(
        view=grid_view, field=formula_field, order="DESC"
    )
    sorted_rows = view_handler.apply_sorting(grid_view, model.objects.all())
    sorted_lookup = [
        getattr(r, f"field_{formula_field.id}_agg_sort_array") for r in sorted_rows
    ]

    assert sorted_lookup == expected

    sort.order = "ASC"
    sort.save()
    sorted_rows = view_handler.apply_sorting(grid_view, model.objects.all())
    sorted_lookup = [
        getattr(r, f"field_{formula_field.id}_agg_sort_array") for r in sorted_rows
    ]

    expected.reverse()

    assert sorted_lookup == expected


@pytest.mark.django_db
def test_formula_field_type_lookup_sorting_array_numbers(
    data_fixture,
):
    def create_primary_field(table):
        return data_fixture.create_number_field(
            table=table, order=1, primary=True, name="number"
        )

    formula_type = "number"
    distinct_values = [1, 2, 11, 22, 111, None]
    unsorted_rows = [
        [Decimal("2"), Decimal("1")],
        [Decimal("1")],
        [Decimal("1"), Decimal("2")],
        [],
        [Decimal("2"), Decimal("111")],
        [Decimal("2")],
        [None],
        [Decimal("11")],
    ]

    model, formula_field, grid_view = _create_arr_sort_fixture(
        data_fixture, create_primary_field, formula_type, distinct_values, unsorted_rows
    )

    expected = [
        [None],
        [Decimal("11")],
        [Decimal("2"), Decimal("111")],
        [Decimal("2")],
        [Decimal("1"), Decimal("2")],
        [Decimal("1"), Decimal("2")],
        [Decimal("1")],
        None,
    ]

    view_handler = ViewHandler()
    sort = data_fixture.create_view_sort(
        view=grid_view, field=formula_field, order="DESC"
    )
    sorted_rows = view_handler.apply_sorting(grid_view, model.objects.all())
    sorted_lookup = [
        getattr(r, f"field_{formula_field.id}_agg_sort_array") for r in sorted_rows
    ]

    assert sorted_lookup == expected

    sort.order = "ASC"
    sort.save()
    sorted_rows = view_handler.apply_sorting(grid_view, model.objects.all())
    sorted_lookup = [
        getattr(r, f"field_{formula_field.id}_agg_sort_array") for r in sorted_rows
    ]

    expected.reverse()

    assert sorted_lookup == expected


@pytest.mark.django_db
def test_formula_field_type_lookup_sorting_array_numbers_fractions(
    data_fixture,
):
    def create_primary_field(table):
        return data_fixture.create_number_field(
            table=table, order=1, primary=True, name="number", number_decimal_places=2
        )

    formula_type = "number"
    distinct_values = [
        Decimal("1.00"),
        Decimal("1.60"),
        Decimal("111.00"),
        Decimal("2.20"),
        Decimal("2.32"),
        Decimal("1.50"),
        Decimal("2.00"),
        Decimal("2.33"),
        None,
    ]
    unsorted_rows = [
        [Decimal("1.60"), Decimal("1.00")],
        [Decimal("2.20")],
        [Decimal("2.32"), Decimal("2.00")],
        [],
        [Decimal("1.50"), Decimal("111.00")],
        [Decimal("2.00")],
        [None],
        [Decimal("2.33")],
    ]

    model, formula_field, grid_view = _create_arr_sort_fixture(
        data_fixture, create_primary_field, formula_type, distinct_values, unsorted_rows
    )

    expected = [
        [None],
        [Decimal("111.00"), Decimal("1.50")],
        [Decimal("2.33")],
        [Decimal("2.32"), Decimal("2.00")],
        [Decimal("2.20")],
        [Decimal("2.00")],
        [Decimal("1.00"), Decimal("1.60")],
        None,
    ]

    view_handler = ViewHandler()
    sort = data_fixture.create_view_sort(
        view=grid_view, field=formula_field, order="DESC"
    )
    sorted_rows = view_handler.apply_sorting(grid_view, model.objects.all())
    sorted_lookup = [
        getattr(r, f"field_{formula_field.id}_agg_sort_array") for r in sorted_rows
    ]

    assert sorted_lookup == expected

    sort.order = "ASC"
    sort.save()
    sorted_rows = view_handler.apply_sorting(grid_view, model.objects.all())
    sorted_lookup = [
        getattr(r, f"field_{formula_field.id}_agg_sort_array") for r in sorted_rows
    ]

    expected.reverse()

    assert sorted_lookup == expected


@pytest.mark.django_db
def test_formula_field_type_lookup_sorting_array_boolean(
    data_fixture,
):
    def create_primary_field(table):
        return data_fixture.create_boolean_field(
            table=table, order=1, primary=True, name="boolean"
        )

    distinct_values = [True, False]
    formula_type = "boolean"
    unsorted_rows = [
        [False, True],
        [True],
        [True, False],
        [],
        [False, True],
        [False],
        [True],
    ]
    model, formula_field, grid_view = _create_arr_sort_fixture(
        data_fixture, create_primary_field, formula_type, distinct_values, unsorted_rows
    )

    expected = [
        [True, False],
        [True, False],
        [True, False],
        [True],
        [True],
        [False],
        None,
    ]

    view_handler = ViewHandler()
    sort = data_fixture.create_view_sort(
        view=grid_view, field=formula_field, order="DESC"
    )
    sorted_rows = view_handler.apply_sorting(grid_view, model.objects.all())
    sorted_lookup = [
        getattr(r, f"field_{formula_field.id}_agg_sort_array") for r in sorted_rows
    ]

    assert sorted_lookup == expected

    sort.order = "ASC"
    sort.save()
    sorted_rows = view_handler.apply_sorting(grid_view, model.objects.all())
    sorted_lookup = [
        getattr(r, f"field_{formula_field.id}_agg_sort_array") for r in sorted_rows
    ]

    expected.reverse()

    assert sorted_lookup == expected


@pytest.mark.django_db
def test_formula_field_type_lookup_sorting_single_select(
    data_fixture,
):
    row_handler = RowHandler()
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="db")

    # related table
    related_table = data_fixture.create_database_table(
        name="Related table", database=database
    )
    related_primary_field = data_fixture.create_single_select_field(
        table=related_table, order=1, primary=True, name="Primary text"
    )
    distinct_values = ["a", "b", "aa", "bb", "aaa", None]
    distinct_values_id_mapping = {}
    for dv in distinct_values:
        if dv:
            option = data_fixture.create_select_option(
                field=related_primary_field, value=dv, color="blue"
            )
        else:
            option = None
        distinct_values_id_mapping[dv] = option

    related_table_model = related_table.get_model()
    related_table_rows = {}
    for dv in distinct_values:
        related_table_rows[dv] = related_table_model.objects.create(
            **{f"field_{related_primary_field.id}": distinct_values_id_mapping[dv]}
        )

    # main table
    table = data_fixture.create_database_table(name="Main table", database=database)
    data_fixture.create_text_field(
        table=table, order=1, primary=True, name="Primary text"
    )
    link_row_field = data_fixture.create_link_row_field(
        name="link", table=table, link_row_table=related_table
    )
    formula_field = data_fixture.create_formula_field(
        table=table,
        name="formula_lookup",
        formula=f"lookup('{link_row_field.name}', '{related_primary_field.name}')",
        formula_type="single_select",
    )
    grid_view = data_fixture.create_grid_view(table=table)

    unsorted_rows = [
        ["b", "a"],
        ["a"],
        ["a", "b"],
        [],
        ["b", "aaa"],
        ["b"],
        ["aa"],
        [None],
    ]

    for index, field_values in enumerate(unsorted_rows):
        for index2, value in enumerate(field_values):
            unsorted_rows[index][index2] = related_table_rows[value].id

    for row_list in unsorted_rows:
        row_handler.create_row(
            user=user, table=table, values={f"field_{link_row_field.id}": row_list}
        )

    expected = [
        [None],
        ["b", "aaa"],
        ["b"],
        ["aa"],
        ["a", "b"],
        ["a", "b"],
        ["a"],
        None,
    ]

    view_handler = ViewHandler()
    sort = data_fixture.create_view_sort(
        view=grid_view, field=formula_field, order="DESC"
    )
    model = table.get_model()
    sorted_rows = view_handler.apply_sorting(grid_view, model.objects.all())

    sorted_lookup = [
        getattr(r, f"field_{formula_field.id}_agg_sort_array") for r in sorted_rows
    ]

    assert sorted_lookup == expected

    sort.order = "ASC"
    sort.save()
    sorted_rows = view_handler.apply_sorting(grid_view, model.objects.all())
    sorted_lookup = [
        getattr(r, f"field_{formula_field.id}_agg_sort_array") for r in sorted_rows
    ]

    expected.reverse()

    assert sorted_lookup == expected


@pytest.mark.django_db
def test_formula_field_type_lookup_sorting_array_datetimes(
    data_fixture,
):
    def create_primary_field(table):
        return data_fixture.create_date_field(
            table=table, order=1, primary=True, name="date", date_include_time=True
        )

    formula_type = "date"
    distinct_values = [
        datetime(2020, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
        datetime(2020, 1, 1, 15, 0, tzinfo=ZoneInfo("UTC")),
        datetime(2020, 1, 1, 15, 15, tzinfo=ZoneInfo("UTC")),
        datetime(2020, 1, 2, 0, 0, tzinfo=ZoneInfo("UTC")),
        datetime(2020, 1, 2, 15, 0, tzinfo=ZoneInfo("UTC")),
        datetime(2020, 1, 2, 15, 15, tzinfo=ZoneInfo("UTC")),
        datetime(2020, 2, 15, 0, 0, tzinfo=ZoneInfo("UTC")),
        datetime(2020, 2, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
        None,
    ]
    unsorted_rows = [
        [
            datetime(2020, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
            datetime(2020, 1, 2, 0, 0, tzinfo=ZoneInfo("UTC")),
        ],
        [
            datetime(2020, 1, 1, 15, 15, tzinfo=ZoneInfo("UTC")),
            datetime(2020, 1, 2, 15, 15, tzinfo=ZoneInfo("UTC")),
        ],
        [
            datetime(2020, 1, 1, 15, 15, tzinfo=ZoneInfo("UTC")),
            datetime(2020, 2, 15, 0, 0, tzinfo=ZoneInfo("UTC")),
        ],
        [],
        [datetime(2020, 2, 1, 0, 0, tzinfo=ZoneInfo("UTC"))],
        [datetime(2020, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))],
        [None],
        [datetime(2020, 2, 15, 0, 0, tzinfo=ZoneInfo("UTC"))],
    ]

    model, formula_field, grid_view = _create_arr_sort_fixture(
        data_fixture, create_primary_field, formula_type, distinct_values, unsorted_rows
    )

    expected = [
        [None],
        [datetime(2020, 2, 15, 0, 0)],
        [datetime(2020, 2, 1, 0, 0)],
        [
            datetime(2020, 1, 1, 15, 15),
            datetime(2020, 2, 15, 0, 0),
        ],
        [
            datetime(2020, 1, 1, 15, 15),
            datetime(2020, 1, 2, 15, 15),
        ],
        [
            datetime(2020, 1, 1, 0, 0),
            datetime(2020, 1, 2, 0, 0),
        ],
        [datetime(2020, 1, 1, 0, 0)],
        None,
    ]

    view_handler = ViewHandler()
    sort = data_fixture.create_view_sort(
        view=grid_view, field=formula_field, order="DESC"
    )
    sorted_rows = view_handler.apply_sorting(grid_view, model.objects.all())
    sorted_lookup = [
        getattr(r, f"field_{formula_field.id}_agg_sort_array") for r in sorted_rows
    ]

    assert sorted_lookup == expected

    sort.order = "ASC"
    sort.save()
    sorted_rows = view_handler.apply_sorting(grid_view, model.objects.all())
    sorted_lookup = [
        getattr(r, f"field_{formula_field.id}_agg_sort_array") for r in sorted_rows
    ]

    expected.reverse()

    assert sorted_lookup == expected


@pytest.mark.django_db
def test_formula_field_type_lookup_sorting_array_dates(
    data_fixture,
):
    def create_primary_field(table):
        return data_fixture.create_date_field(
            table=table, order=1, primary=True, name="date", date_include_time=False
        )

    formula_type = "date"
    distinct_values = [
        datetime(2020, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
        datetime(2020, 1, 1, 15, 0, tzinfo=ZoneInfo("UTC")),
        datetime(2020, 1, 1, 15, 15, tzinfo=ZoneInfo("UTC")),
        datetime(2020, 1, 2, 0, 0, tzinfo=ZoneInfo("UTC")),
        datetime(2020, 1, 2, 15, 0, tzinfo=ZoneInfo("UTC")),
        datetime(2020, 1, 2, 15, 15, tzinfo=ZoneInfo("UTC")),
        datetime(2020, 2, 15, 0, 0, tzinfo=ZoneInfo("UTC")),
        datetime(2020, 2, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
        None,
    ]
    unsorted_rows = [
        [
            datetime(2020, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
            datetime(2020, 1, 2, 0, 0, tzinfo=ZoneInfo("UTC")),
        ],
        [
            datetime(2020, 1, 1, 15, 15, tzinfo=ZoneInfo("UTC")),
            datetime(2020, 1, 2, 15, 15, tzinfo=ZoneInfo("UTC")),
        ],
        [
            datetime(2020, 1, 1, 15, 15, tzinfo=ZoneInfo("UTC")),
            datetime(2020, 2, 15, 0, 0, tzinfo=ZoneInfo("UTC")),
        ],
        [],
        [datetime(2020, 2, 1, 0, 0, tzinfo=ZoneInfo("UTC"))],
        [datetime(2020, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))],
        [None],
        [datetime(2020, 2, 15, 0, 0, tzinfo=ZoneInfo("UTC"))],
    ]

    model, formula_field, grid_view = _create_arr_sort_fixture(
        data_fixture, create_primary_field, formula_type, distinct_values, unsorted_rows
    )

    expected = [
        [None],
        [datetime(2020, 2, 15, 0, 0)],
        [datetime(2020, 2, 1, 0, 0)],
        [
            datetime(2020, 1, 1, 0, 0),
            datetime(2020, 2, 15, 0, 0),
        ],
        [
            datetime(2020, 1, 1, 0, 0),
            datetime(2020, 1, 2, 0, 0),
        ],
        [
            datetime(2020, 1, 1, 0, 0),
            datetime(2020, 1, 2, 0, 0),
        ],
        [datetime(2020, 1, 1, 0, 0)],
        None,
    ]

    view_handler = ViewHandler()
    sort = data_fixture.create_view_sort(
        view=grid_view, field=formula_field, order="DESC"
    )
    sorted_rows = view_handler.apply_sorting(grid_view, model.objects.all())
    sorted_lookup = [
        getattr(r, f"field_{formula_field.id}_agg_sort_array") for r in sorted_rows
    ]

    assert sorted_lookup == expected

    sort.order = "ASC"
    sort.save()
    sorted_rows = view_handler.apply_sorting(grid_view, model.objects.all())
    sorted_lookup = [
        getattr(r, f"field_{formula_field.id}_agg_sort_array") for r in sorted_rows
    ]

    expected.reverse()

    assert sorted_lookup == expected


@pytest.mark.django_db
def test_formula_single_select_field_type_sorting(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)
    field = data_fixture.create_single_select_field(table=table)
    option_c = data_fixture.create_select_option(field=field, value="C", color="blue")
    option_a = data_fixture.create_select_option(field=field, value="A", color="blue")
    option_b = data_fixture.create_select_option(field=field, value="B", color="blue")
    formula_field = data_fixture.create_formula_field(
        table=table,
        name="formula",
        formula=f"field('{field.name}')",
        formula_type="single_select",
    )
    grid_view = data_fixture.create_grid_view(table=table)

    view_handler = ViewHandler()
    row_handler = RowHandler()

    row_1 = row_handler.create_row(
        user=user, table=table, values={f"field_{field.id}": option_b.id}
    )
    row_2 = row_handler.create_row(
        user=user, table=table, values={f"field_{field.id}": option_a.id}
    )
    row_3 = row_handler.create_row(
        user=user, table=table, values={f"field_{field.id}": option_c.id}
    )
    row_4 = row_handler.create_row(
        user=user, table=table, values={f"field_{field.id}": option_b.id}
    )
    row_5 = row_handler.create_row(
        user=user, table=table, values={f"field_{field.id}": None}
    )

    sort = data_fixture.create_view_sort(
        view=grid_view, field=formula_field, order="ASC"
    )
    model = table.get_model()
    rows = view_handler.apply_sorting(grid_view, model.objects.all())

    row_ids = [row.id for row in rows]
    assert row_ids == [row_5.id, row_2.id, row_1.id, row_4.id, row_3.id]

    sort.order = "DESC"
    sort.save()
    rows = view_handler.apply_sorting(grid_view, model.objects.all())
    row_ids = [row.id for row in rows]
    assert row_ids == [row_3.id, row_1.id, row_4.id, row_2.id, row_5.id]

    sort.order = "ASC"
    sort.save()
    model = table.get_model()
    rows = view_handler.apply_sorting(grid_view, model.objects.all())
    row_ids = [row.id for row in rows]
    assert row_ids == [row_5.id, row_2.id, row_1.id, row_4.id, row_3.id]


@pytest.mark.django_db
def test_formula_text_field_type_get_order_collate(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    text_field = data_fixture.create_text_field(
        table=table, name="field", order=1, primary=True
    )
    formula_field = data_fixture.create_formula_field(
        table=table, formula="field('field')", formula_type="text"
    )

    model = table.get_model()

    dir_path = os.path.dirname(os.path.realpath(__file__))
    with open(
        dir_path + "/../../../../../../tests/all_chars.txt", mode="r", encoding="utf-8"
    ) as f:
        all_chars = f.read()
    with open(
        dir_path + "/../../../../../../tests/sorted_chars.txt",
        mode="r",
        encoding="utf-8",
    ) as f:
        sorted_chars = f.read()

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {
                f"field_{text_field.id}": char,
            }
            for char in all_chars
        ],
    )

    queryset = model.objects.all().order_by_fields_string(f"field_{formula_field.id}")
    result = ""
    for char in queryset:
        result += getattr(char, f"field_{formula_field.id}")

    assert result == sorted_chars


@pytest.mark.django_db
def test_formula_number_type_without_decimal_places(data_fixture):
    """
    Tests if a number formula field will be processed properly, if there's no
    number_decimal_places value defined for the field.

    See: https://gitlab.com/baserow/baserow/-/issues/3616

    A FormulaField instance may end up in a state, where the type is set to `number`,
    but there's no value in .number_decimal_places. This value is used in several
    field operations, and `None` was causing an error.

    While the cause of this invalid state is not entirely known, the fix works around
    the missing part by replacing `None` with a number.
    """

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    handler = FieldHandler()
    formula_field: FormulaField = handler.create_field(
        user=user, table=table, name="1", type_name="formula", formula="1+1"
    )

    # Simulate error condition - formula field is of type `number`, but it has no
    # number_decimal_places value.
    formula_field.number_decimal_places = None
    formula_field.save()

    # the fix in NumerFieldType.from_baserow_formula_type replaces `None` with `0`,
    # otherwise the operation below would fail.
    FieldHandler().duplicate_field(user, formula_field, duplicate_data=True)


@pytest.mark.django_db
def test_can_export_import_database_with_broken_via_dependency(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table_1 = data_fixture.create_database_table(database=database)
    table_1_field_1 = data_fixture.create_text_field(
        table=table_1, name="Name", primary=True
    )
    table_2 = data_fixture.create_database_table(database=database)
    table_2_field_1 = data_fixture.create_text_field(
        table=table_2, name="Name", primary=True
    )

    field_handler = FieldHandler()
    link_row_field = field_handler.create_field(
        user=user,
        table=table_2,
        type_name="link_row",
        name="Link",
        link_row_table=table_1,
    )
    formula_field = field_handler.create_field(
        user,
        table_2,
        name="Lookup",
        type_name="formula",
        formula=f"lookup('{link_row_field.name}', '{table_1_field_1.name}')",
    )

    field_handler.delete_field(user, link_row_field)
    formula_field.refresh_from_db()
    assert formula_field.formula_type == "invalid"

    duplicated_database = CoreHandler().duplicate_application(user, database)
    duplicated_tables = duplicated_database.table_set.all()
    duplicated_formula = (
        duplicated_tables[1].field_set.filter(name="Lookup")[0].specific
    )
    assert duplicated_formula.formula_type == "invalid"

    # Fix the broken via dependency by creating the missing field.
    field_handler.create_field(
        user=user,
        table=duplicated_tables[1],
        type_name="link_row",
        name="Link",
        link_row_table=duplicated_tables[0],
    )

    duplicated_formula.refresh_from_db()
    assert duplicated_formula.formula_type == "array"


@pytest.mark.django_db
def test_count_formula_for_link_row_field_with_null_values(data_fixture):
    user = data_fixture.create_user()

    table_a = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table_a, name="Field A", primary=True)

    table_b = data_fixture.create_database_table(user=user)
    data_fixture.create_date_field(table=table_b, name="Field B", primary=True)
    link_field = data_fixture.create_link_row_field(
        table=table_a,
        link_row_table=table_b,
        name="Link",
    )
    formula_field = data_fixture.create_formula_field(
        table=table_a,
        name="Count",
        formula="count(field('Link'))",
    )

    row_handler = RowHandler()
    rows = row_handler.create_rows(
        user=user, table=table_b, rows_values=[{}, {}, {}], model=table_b.get_model()
    ).created_rows

    row_a = row_handler.create_row(
        user=user,
        table=table_a,
        values={link_field.db_column: [row.id for row in rows]},
    )

    assert getattr(row_a, formula_field.db_column) == 3
