import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler


@pytest.mark.django_db
def test_three_table_dependency_ordering_when_deleting_row(data_fixture):
    user = data_fixture.create_user()

    database = data_fixture.create_database_application(user=user, name="Test Database")

    table_a = data_fixture.create_database_table(
        user=user, database=database, name="Table A"
    )
    table_b = data_fixture.create_database_table(
        user=user, database=database, name="Table B"
    )
    table_c = data_fixture.create_database_table(
        user=user, database=database, name="Table C"
    )

    primary_a = data_fixture.create_text_field(name="Name", table=table_a, primary=True)
    primary_b = data_fixture.create_text_field(name="Name", table=table_b, primary=True)
    primary_c = data_fixture.create_text_field(name="Name", table=table_c, primary=True)

    field_handler = FieldHandler()

    value_field = data_fixture.create_number_field(
        name="Value",
        table=table_a,
        number_decimal_places=0,
        number_negative=False,
    )

    link_a_to_b = field_handler.create_field(
        user,
        table_a,
        "link_row",
        name="Related B",
        link_row_table=table_b,
        has_related_field=True,
    )
    link_b_to_a = link_a_to_b.link_row_related_field

    multiplier_field = data_fixture.create_number_field(
        name="Multiplier",
        table=table_b,
        number_decimal_places=0,
        number_negative=False,
    )

    link_b_to_c = field_handler.create_field(
        user,
        table_b,
        "link_row",
        name="Related C",
        link_row_table=table_c,
        has_related_field=True,
    )
    link_c_to_b = link_b_to_c.link_row_related_field

    total_field = field_handler.create_field(
        user,
        table_b,
        "rollup",
        name="Total",
        through_field_id=link_b_to_a.id,
        target_field_id=value_field.id,
        rollup_function="sum",
    )

    calculated_field = field_handler.create_field(
        user,
        table_b,
        "formula",
        name="Calculated",
        formula="field('Multiplier') * field('Total')",
        formula_type="number",
    )

    result_field = field_handler.create_field(
        user,
        table_c,
        "rollup",
        name="Result",
        through_field_id=link_c_to_b.id,
        target_field_id=calculated_field.id,
        rollup_function="sum",
    )

    row_handler = RowHandler()

    row_c1 = row_handler.force_create_row(user, table_c, {primary_c.db_column: "C1"})

    row_b1 = row_handler.force_create_row(
        user,
        table_b,
        {
            primary_b.db_column: "B1",
            multiplier_field.db_column: 120,
            link_b_to_c.db_column: [row_c1.id],
        },
    )

    row_a1 = row_handler.force_create_row(
        user,
        table_a,
        {
            primary_a.db_column: "A1",
            value_field.db_column: 100,
            link_a_to_b.db_column: [row_b1.id],
        },
    )

    row_a2 = row_handler.force_create_row(
        user,
        table_a,
        {
            primary_a.db_column: "A2",
            value_field.db_column: 50,
            link_a_to_b.db_column: [row_b1.id],
        },
    )

    row_b1.refresh_from_db()
    row_c1.refresh_from_db()

    initial_total = getattr(row_b1, total_field.db_column)
    initial_calculated = getattr(row_b1, calculated_field.db_column)
    initial_result = getattr(row_c1, result_field.db_column)

    assert initial_total == 150  # 100 + 50
    assert initial_calculated == 18000  # 120 * 150
    assert initial_result == 18000

    row_handler.delete_row_by_id(user, table_a, row_a1.id)

    row_b1.refresh_from_db()
    row_c1.refresh_from_db()

    final_total = getattr(row_b1, total_field.db_column)
    final_calculated = getattr(row_b1, calculated_field.db_column)
    final_result = getattr(row_c1, result_field.db_column)

    assert final_total == 50, f"Total should be 50, got {final_total}"
    assert final_calculated == 6000  # 120 * 50
    assert final_result == 6000


@pytest.mark.django_db
def test_two_table_dependency_ordering_when_deleting_row(data_fixture):
    user = data_fixture.create_user()

    database = data_fixture.create_database_application(user=user, name="Test Database")

    table_a = data_fixture.create_database_table(
        user=user, database=database, name="Table A"
    )
    table_b = data_fixture.create_database_table(
        user=user, database=database, name="Table B"
    )

    data_fixture.create_text_field(name="Name", table=table_a, primary=True)
    data_fixture.create_text_field(name="Name", table=table_b, primary=True)

    value_field = data_fixture.create_number_field(name="Value", table=table_a)

    multiplier_field = data_fixture.create_number_field(
        name="Multiplier", table=table_b
    )

    field_handler = FieldHandler()
    link_a_to_b = field_handler.create_field(
        user,
        table_a,
        "link_row",
        name="Related B",
        link_row_table=table_b,
        has_related_field=True,
    )
    link_b_to_a = link_a_to_b.link_row_related_field

    total_field = field_handler.create_field(
        user,
        table_b,
        "rollup",
        name="Total",
        through_field_id=link_b_to_a.id,
        target_field_id=value_field.id,
        rollup_function="sum",
    )

    result_field = field_handler.create_field(
        user,
        table_b,
        "formula",
        name="Result",
        formula="field('Multiplier') * field('Total')",
        formula_type="number",
    )

    row_handler = RowHandler()

    row_b1 = row_handler.force_create_row(
        user, table_b, {multiplier_field.db_column: 2}
    )
    row_b2 = row_handler.force_create_row(
        user, table_b, {multiplier_field.db_column: 3}
    )

    row_a1 = row_handler.force_create_row(
        user,
        table_a,
        {
            value_field.db_column: 10,
            link_a_to_b.db_column: [row_b1.id, row_b2.id],
        },
    )

    row_b1.refresh_from_db()
    row_b2.refresh_from_db()

    assert getattr(row_b1, total_field.db_column) == 10
    assert getattr(row_b1, result_field.db_column) == 20  # 2 * 10
    assert getattr(row_b2, total_field.db_column) == 10
    assert getattr(row_b2, result_field.db_column) == 30  # 3 * 10

    row_handler.delete_row_by_id(user, table_a, row_a1.id)

    row_b1.refresh_from_db()
    row_b2.refresh_from_db()

    assert getattr(row_b1, total_field.db_column) == 0
    assert getattr(row_b1, result_field.db_column) == 0
    assert getattr(row_b2, total_field.db_column) == 0
    assert getattr(row_b2, result_field.db_column) == 0
