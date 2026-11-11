"""Kuma-database-formulas eval dataset: formula and lookup fields."""

from __future__ import annotations

from decimal import Decimal

from baserow.contrib.database.fields.models import (
    FormulaField,
    LinkRowField,
    LookupField,
)
from baserow.contrib.database.models import Table
from baserow.core.db import specific_iterator
from baserow.test_utils.fixtures import Fixtures
from baserow_enterprise.assistant.evals.registry import (
    register_case,
    register_scenario,
)
from baserow_enterprise.assistant.evals.scenarios import build_database_ui_context
from baserow_enterprise.assistant.evals.types import (
    CheckResult,
    EvalCase,
    EvalRunOutput,
    EvalScenario,
)

DATASET = "kuma-database-formulas"


def _fields(table: Table) -> list:
    return list(specific_iterator(table.field_set.all()))


def _named(fields: list, *keywords: str):
    return next((f for f in fields if all(k in f.name.lower() for k in keywords)), None)


def _first_row_value(table: Table, field) -> object:
    model = table.get_model()
    row = model.objects.order_by("id").first()
    return getattr(row, field.db_column) if row and field else None


def _valid_formula_checks(label: str, field) -> list[CheckResult]:
    return [
        CheckResult(f"{label} field exists", field is not None),
        CheckResult(
            f"{label} is a valid formula or lookup",
            field is not None
            and isinstance(field, FormulaField)
            and not field.error
            and field.formula_type != "invalid",
            hint=(
                f"type={type(field).__name__}, "
                f"formula={getattr(field, 'formula', None)!r}, "
                f"error={getattr(field, 'error', None)!r}"
                if field
                else "missing"
            ),
        ),
    ]


def _lookup_values(value) -> list:
    return [
        item.get("value") if isinstance(item, dict) else item for item in value or []
    ]


# ---------------------------------------------------------------------------
# Orders table with a seeded row: Name "A", Qty 3, Price 2.50
# ---------------------------------------------------------------------------


@register_scenario("database-formulas-orders")
def _orders_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(workspace=workspace, name="Shop")
    table = fx.create_database_table(database=database, name="Orders")
    name = fx.create_text_field(table=table, name="Name", primary=True)
    qty = fx.create_number_field(table=table, name="Qty")
    price = fx.create_number_field(table=table, name="Price", number_decimal_places=2)
    table.get_model().objects.create(
        **{name.db_column: "A", qty.db_column: 3, price.db_column: Decimal("2.50")}
    )
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database, table),
        refs={"table": table},
    )


def _check_total_from_description(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    table = scenario.refs["table"]
    total = _named(_fields(table), "total")
    value = _first_row_value(table, total)
    return _valid_formula_checks("Total", total) + [
        CheckResult(
            "Total is Qty * Price on the seeded row",
            value is not None and Decimal(str(value)) == Decimal("7.5"),
            hint=f"value={value!r}",
        ),
    ]


register_case(
    EvalCase(
        id="database/formula-from-description",
        dataset=DATASET,
        prompt="Add a Total field to the Orders table that multiplies Qty by Price.",
        scenario="database-formulas-orders",
        checks=_check_total_from_description,
        max_iters=15,
    )
)


def _check_raw_formula(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    table = scenario.refs["table"]
    label = _named(_fields(table), "label")
    value = _first_row_value(table, label)
    return _valid_formula_checks("Label", label) + [
        CheckResult(
            "Label computes 'A x3' on the seeded row",
            value == "A x3",
            hint=f"value={value!r}",
        ),
    ]


register_case(
    EvalCase(
        id="database/formula-raw-from-user",
        dataset=DATASET,
        prompt=(
            "Add a formula field called Label to the Orders table with exactly this "
            "formula: concat(field('Name'), ' x', field('Qty'))"
        ),
        scenario="database-formulas-orders",
        checks=_check_raw_formula,
        max_iters=15,
    )
)


def _check_invalid_formula_repaired(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    table = scenario.refs["table"]
    fields = _fields(table)
    rounded = _named(fields, "rounded")
    value = _first_row_value(table, rounded)
    return _valid_formula_checks("Rounded", rounded) + [
        CheckResult(
            "Rounded is Price * 0.9 rounded on the seeded row",
            value is not None
            and Decimal(str(value)) in (Decimal("2"), Decimal("2.3"), Decimal("2.25")),
            hint=f"value={value!r}",
        ),
        CheckResult(
            "Only one Rounded field",
            sum(1 for f in fields if "rounded" in f.name.lower()) == 1,
            hint=f"fields: {[f.name for f in fields]}",
        ),
    ]


register_case(
    EvalCase(
        id="database/formula-invalid-from-user-is-repaired",
        dataset=DATASET,
        # Baserow's round() needs the number of decimal places, so the formula is
        # invalid as given and has to be repaired.
        prompt=(
            "Add a formula field Rounded to the Orders table with the formula "
            "round(field('Price') * 0.9)"
        ),
        scenario="database-formulas-orders",
        checks=_check_invalid_formula_repaired,
        max_iters=15,
        max_tool_errors=1,
    )
)


# ---------------------------------------------------------------------------
# Projects <- Tasks link, with a seeded linked row
# ---------------------------------------------------------------------------


@register_scenario("database-formulas-projects-tasks")
def _projects_tasks_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(workspace=workspace, name="Work")
    projects = fx.create_database_table(database=database, name="Projects")
    project_name = fx.create_text_field(table=projects, name="Name", primary=True)
    owner = fx.create_text_field(table=projects, name="Owner")
    tasks = fx.create_database_table(database=database, name="Tasks")
    task_title = fx.create_text_field(table=tasks, name="Title", primary=True)
    link = fx.create_link_row_field(
        table=tasks, name="Project", link_row_table=projects
    )
    project = projects.get_model().objects.create(
        **{project_name.db_column: "Apollo", owner.db_column: "Ada"}
    )
    task = tasks.get_model().objects.create(**{task_title.db_column: "Launch"})
    getattr(task, link.db_column).set([project.id])
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database, tasks),
        refs={"tasks": tasks, "link": link},
    )


def _check_lookup_through_existing_link(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    tasks = scenario.refs["tasks"]
    fields = _fields(tasks)
    owner = _named(fields, "owner")
    value = _first_row_value(tasks, owner)
    links = [f for f in fields if isinstance(f, LinkRowField)]
    return _valid_formula_checks("Owner lookup", owner) + [
        CheckResult(
            "Owner shows 'Ada' on the seeded task",
            _lookup_values(value) == ["Ada"],
            hint=f"value={value!r}",
        ),
        CheckResult(
            "No new link field created",
            len(links) == 1,
            hint=f"link fields: {[f.name for f in links]}",
        ),
    ]


register_case(
    EvalCase(
        id="database/lookup-through-existing-link",
        dataset=DATASET,
        prompt="In the Tasks table, add a field that shows the Owner of each task's project.",
        scenario="database-formulas-projects-tasks",
        checks=_check_lookup_through_existing_link,
        max_iters=15,
    )
)


# ---------------------------------------------------------------------------
# New linked tables with a lookup and a formula in one request
# ---------------------------------------------------------------------------


@register_scenario("database-formulas-empty-database")
def _empty_database_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(workspace=workspace, name="Sales")
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database),
        refs={"database": database},
    )


def _check_tables_with_lookup_and_formula(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    tables = {
        t.name.lower(): t
        for t in Table.objects.filter(database=scenario.refs["database"])
    }
    customers = next((t for n, t in tables.items() if "customer" in n), None)
    orders = next((t for n, t in tables.items() if "order" in n), None)
    fields = _fields(orders) if orders else []
    link = next(
        (
            f
            for f in fields
            if isinstance(f, LinkRowField)
            and customers
            and f.link_row_table_id == customers.id
        ),
        None,
    )
    country = next(
        (
            f
            for f in fields
            if "country" in f.name.lower() and isinstance(f, FormulaField)
        ),
        None,
    )
    vat = _named(fields, "vat")
    return (
        [
            CheckResult(
                "Customers and Orders tables created",
                customers is not None and orders is not None,
                hint=f"tables: {list(tables)}",
            ),
            CheckResult("Orders links to Customers", link is not None),
            CheckResult(
                "Country is a lookup (or lookup formula) in Orders",
                country is not None
                and (isinstance(country, LookupField) or "lookup" in country.formula),
                hint=f"fields: {[(f.name, type(f).__name__) for f in fields]}",
            ),
        ]
        + _valid_formula_checks("Country", country)
        + _valid_formula_checks("Amount with VAT", vat)
    )


register_case(
    EvalCase(
        id="database/creates-tables-with-lookup-and-formula",
        dataset=DATASET,
        prompt=(
            "In database Sales, create a Customers table with Name and Country, and "
            "an Orders table with Order Number, Amount (a number) and a link to "
            "Customers. Orders should also show the customer's Country, and an "
            "Amount With VAT field equal to Amount times 1.2. Don't add sample rows."
        ),
        scenario="database-formulas-empty-database",
        checks=_check_tables_with_lookup_and_formula,
        max_iters=20,
    )
)
