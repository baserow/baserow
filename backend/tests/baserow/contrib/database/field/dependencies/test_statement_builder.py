from decimal import Decimal
from unittest.mock import patch

import pytest

from baserow.contrib.database.fields.dependencies.handler import (
    FieldDependencyHandler,
)
from baserow.contrib.database.fields.field_cache import FieldCache
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler


def create_companies_and_deals(data_fixture):
    """
    Creates a Companies table with every aggregate formula shape over a linked
    Deals table: lookup arrays, rollups, count, sum/avg/filtered count
    formulas, a joined text aggregate and a chained scalar formula.
    """

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    companies = data_fixture.create_database_table(user=user, database=database)
    deals = data_fixture.create_database_table(user=user, database=database)
    data_fixture.create_text_field(table=companies, name="Name", primary=True)
    deal_name = data_fixture.create_text_field(table=deals, name="Name", primary=True)
    handler = FieldHandler()
    amount = handler.create_field(
        user, deals, "number", name="Amount", number_decimal_places=2
    )
    link = handler.create_field(
        user,
        deals,
        "link_row",
        name="Company",
        link_row_table=companies,
    )
    reverse_link_name = link.link_row_related_field.name
    fields = {
        "amounts": handler.create_field(
            user,
            companies,
            "lookup",
            name="Amounts",
            through_field_name=reverse_link_name,
            target_field_name="Amount",
        ),
        "total": handler.create_field(
            user,
            companies,
            "rollup",
            name="Total",
            through_field_id=link.link_row_related_field_id,
            target_field_id=amount.id,
            rollup_function="sum",
        ),
        "max": handler.create_field(
            user,
            companies,
            "rollup",
            name="Max",
            through_field_id=link.link_row_related_field_id,
            target_field_id=amount.id,
            rollup_function="max",
        ),
        "count": handler.create_field(
            user,
            companies,
            "count",
            name="Deal count",
            through_field_id=link.link_row_related_field_id,
        ),
        "avg": handler.create_field(
            user,
            companies,
            "formula",
            name="Avg",
            formula=f"avg(lookup('{reverse_link_name}', 'Amount'))",
        ),
        "big": handler.create_field(
            user,
            companies,
            "formula",
            name="Big deals",
            formula=(
                f"count(filter(lookup('{reverse_link_name}', 'Amount'), "
                f"lookup('{reverse_link_name}', 'Amount') > 100))"
            ),
        ),
        "names": handler.create_field(
            user,
            companies,
            "formula",
            name="Deal names",
            formula=f"join(totext(lookup('{reverse_link_name}', 'Name')), ', ')",
        ),
        "chained": handler.create_field(
            user,
            companies,
            "formula",
            name="Chained",
            formula="field('Total') * 2 + field('Deal count')",
        ),
    }
    return user, companies, deals, deal_name, amount, link, fields


@pytest.mark.django_db
def test_merged_aggregate_scan_calculates_all_aggregate_shapes_correctly(
    data_fixture,
):
    (
        user,
        companies,
        deals,
        deal_name,
        amount,
        link,
        fields,
    ) = create_companies_and_deals(data_fixture)
    companies_model = companies.get_model()
    company = companies_model.objects.create()
    row_handler = RowHandler()
    created = row_handler.force_create_rows(
        user=user,
        table=deals,
        rows_values=[
            {
                f"field_{deal_name.id}": "d1",
                f"field_{amount.id}": "50.00",
                f"field_{link.id}": [company.id],
            },
            {
                f"field_{deal_name.id}": "d2",
                f"field_{amount.id}": "150.00",
                f"field_{link.id}": [company.id],
            },
        ],
    ).created_rows

    # Updating an amount cascades through every aggregate in one merged scan.
    row_handler.force_update_rows(
        user=user,
        table=deals,
        rows_values=[{"id": created[0].id, f"field_{amount.id}": "250.00"}],
    )

    company = companies_model.objects.get(id=company.id)
    values = {key: getattr(company, field.db_column) for key, field in fields.items()}
    assert [float(entry["value"]) for entry in values["amounts"]] == [250.0, 150.0]
    assert values["total"] == Decimal("400.00")
    assert values["max"] == Decimal("250.00")
    assert values["count"] == 2
    assert values["avg"] == Decimal("200.00")
    assert values["big"] == 2
    assert values["names"] == "d1, d2"
    assert values["chained"] == Decimal("802.00")


@pytest.mark.django_db
def test_row_losing_all_links_is_rewritten_to_empty_aggregates(data_fixture):
    (
        user,
        companies,
        deals,
        deal_name,
        amount,
        link,
        fields,
    ) = create_companies_and_deals(data_fixture)
    companies_model = companies.get_model()
    company = companies_model.objects.create()
    row_handler = RowHandler()
    (deal,) = row_handler.force_create_rows(
        user=user,
        table=deals,
        rows_values=[
            {
                f"field_{deal_name.id}": "d1",
                f"field_{amount.id}": "50.00",
                f"field_{link.id}": [company.id],
            }
        ],
    ).created_rows

    # Removing the last connection must still rewrite the company's values,
    # even though it no longer joins back to the deal.
    row_handler.force_update_rows(
        user=user,
        table=deals,
        rows_values=[{"id": deal.id, f"field_{link.id}": []}],
    )

    company = companies_model.objects.get(id=company.id)
    assert getattr(company, fields["amounts"].db_column) == []
    assert getattr(company, fields["total"].db_column) == Decimal("0")
    assert getattr(company, fields["count"].db_column) == 0
    assert getattr(company, fields["names"].db_column) is None


@pytest.mark.django_db
def test_no_op_batch_update_produces_no_dependent_writes_or_side_effects(
    data_fixture,
):
    (
        user,
        companies,
        deals,
        deal_name,
        amount,
        link,
        fields,
    ) = create_companies_and_deals(data_fixture)
    companies_model = companies.get_model()
    company = companies_model.objects.create()
    row_handler = RowHandler()
    (deal,) = row_handler.force_create_rows(
        user=user,
        table=deals,
        rows_values=[
            {
                f"field_{deal_name.id}": "d1",
                f"field_{amount.id}": "50.00",
                f"field_{link.id}": [company.id],
            }
        ],
    ).created_rows

    company_before = companies_model.objects.get(id=company.id)

    with (
        patch(
            "baserow.contrib.database.search.handler.SearchHandler"
            ".schedule_update_search_data"
        ) as search_mock,
        patch(
            "baserow.contrib.database.rows.handler.dependant_rows_updated.send"
        ) as dependant_rows_mock,
    ):
        row_handler.force_update_rows(
            user=user,
            table=deals,
            rows_values=[{"id": deal.id, f"field_{amount.id}": "50.00"}],
        )

    # The written value is identical, so no dependent company row may be
    # rewritten, reindexed or broadcast.
    dependant_rows_mock.assert_not_called()
    scheduled_table_ids = {call.args[0].id for call in search_mock.call_args_list}
    assert companies.id not in scheduled_table_ids
    company_after = companies_model.objects.get(id=company.id)
    assert company_after.updated_on == company_before.updated_on
    for field in fields.values():
        assert getattr(company_after, field.db_column) == getattr(
            company_before, field.db_column
        )


@pytest.mark.django_db
def test_same_table_formula_chain_coalesces_into_one_group_with_correct_values(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    number = data_fixture.create_number_field(table=table, name="a")
    f1 = data_fixture.create_formula_field(
        table=table, name="f1", formula="field('a') + 1"
    )
    f2 = data_fixture.create_formula_field(
        table=table, name="f2", formula="field('f1') * 2"
    )
    # A diamond: f3 depends on both f1 and f2.
    f3 = data_fixture.create_formula_field(
        table=table, name="f3", formula="field('f2') + field('f1')"
    )

    field_cache = FieldCache()
    groups = FieldDependencyHandler.group_all_dependent_fields_by_level(
        table.id, [number.id], field_cache, associated_relations_changed=False
    )
    # The whole same-table chain coalesces into a single statement group,
    # retaining the original dependency depth of every field.
    assert len(groups) == 1
    assert [(entry[0].id, entry[3]) for entry in groups[0]] == [
        (f1.id, 0),
        (f2.id, 1),
        (f3.id, 2),
    ]

    row_handler = RowHandler()
    (row,) = row_handler.force_create_rows(
        user=user, table=table, rows_values=[{f"field_{number.id}": "10"}]
    ).created_rows
    row_handler.force_update_rows(
        user=user,
        table=table,
        rows_values=[{"id": row.id, f"field_{number.id}": "20"}],
    )
    row.refresh_from_db()
    assert getattr(row, f1.db_column) == Decimal("21")
    assert getattr(row, f2.db_column) == Decimal("42")
    assert getattr(row, f3.db_column) == Decimal("63")


@pytest.mark.django_db
def test_self_link_lookup_forces_a_separate_statement_group(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    handler = FieldHandler()
    number = handler.create_field(user, table, "number", name="a")
    self_link = handler.create_field(
        user, table, "link_row", name="Parent", link_row_table=table
    )
    f1 = handler.create_field(
        user, table, "formula", name="f1", formula="field('a') + 1"
    )
    # f2 reads other rows' persisted f1 values through the self-link, so it
    # cannot be calculated in the same statement as f1.
    f2 = handler.create_field(
        user,
        table,
        "formula",
        name="f2",
        formula="sum(lookup('Parent', 'f1'))",
    )

    field_cache = FieldCache()
    groups = FieldDependencyHandler.group_all_dependent_fields_by_level(
        table.id, [number.id], field_cache, associated_relations_changed=False
    )
    assert len(groups) == 2
    assert groups[0][0][0].id == f1.id
    assert groups[1][0][0].id == f2.id

    row_handler = RowHandler()
    (parent,) = row_handler.force_create_rows(
        user=user, table=table, rows_values=[{f"field_{number.id}": "10"}]
    ).created_rows
    (child,) = row_handler.force_create_rows(
        user=user,
        table=table,
        rows_values=[{f"field_{self_link.id}": [parent.id]}],
    ).created_rows

    row_handler.force_update_rows(
        user=user,
        table=table,
        rows_values=[{"id": parent.id, f"field_{number.id}": "40"}],
    )
    parent.refresh_from_db()
    child.refresh_from_db()
    assert getattr(parent, f1.db_column) == Decimal("41")
    assert getattr(child, f2.db_column) == Decimal("41")
