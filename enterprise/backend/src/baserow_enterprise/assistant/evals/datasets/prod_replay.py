"""Kuma-prod-replay eval dataset: production-failure replay prompts.

Every prompt is a synthetic equivalent of a production failure class observed
in error tracing, modeled on the most-repeated request shape of its class.
Each scenario seeds the minimal workspace the prompt assumes and the checks
assert the property that changed: the turn completes and recovers instead of
dying with the class's production exception.

Failure classes, ordered by observed frequency:

- ``'XElement' object has no attribute 'order'`` — the dominant class.
- Wrong/invented ids and view config errors ending the turn.
- Formula compiler errors / tool retry budgets exhausting the turn.
- ``Tool name conflicts with existing tool: 'create_rows_in_table_N'``.
- Row value validation (decimal/date/number got ``''``) ending the turn.
- ``Exceeded maximum output retries (1)`` from the formula agent.

Containment turns these recoverable failures into retry prompts by design, so
each case carries an explicit ``max_tool_errors`` budget instead of the
default 0.
"""

from __future__ import annotations

from baserow.contrib.database.fields.models import FormulaField
from baserow.contrib.database.models import Table
from baserow.contrib.database.views.models import View
from baserow.test_utils.fixtures import Fixtures
from baserow_enterprise.assistant.deps import AgentMode
from baserow_enterprise.assistant.evals.registry import (
    register_case,
    register_scenario,
)
from baserow_enterprise.assistant.evals.scenarios import (
    build_builder_ui_context,
    build_database_ui_context,
)
from baserow_enterprise.assistant.evals.types import (
    CheckResult,
    EvalCase,
    EvalRunOutput,
    EvalScenario,
)

# ---------------------------------------------------------------------------
# Prompts — synthetic equivalents of production failure prompts
# ---------------------------------------------------------------------------

# view_config class: the single most-repeated failing prompt shape.
PROMPT_FORM_FOR_TABLE = "Create a form for this table."

# element_order class: any page inspection died in list_elements.
PROMPT_CHECKBOXES_NOT_ALIGNED = "The checkboxes are not aligned with the rows."

# row_tool_conflict class: onboarding path reloads row tools.
PROMPT_PROJECT_TRACKER = (
    "Create a database including tables, fields, example rows, and example "
    "views matching this description: Create a project tracker with Projects, "
    "Tasks, Assignees, Status, Priority, Due dates."
)

# formula_agent_retries class: one validator rejection exhausted the budget.
PROMPT_ISO_WEEK_FORMULA = (
    "Add a week number column that computes the ISO 8601 week number from "
    "the {Recorded Date} column."
)

# formula_agent_retries class: a request the formula language cannot express.
PROMPT_IMPOSSIBLE_FORMULA = (
    "Write a formula that fetches the image found at the URL in the "
    "{Product Page URL} field."
)

# row_validation class: typed fields got '' and the turn died.
PROMPT_FAKE_MEMBER_ROWS = (
    "Generate 50 fake gym members with:\n\n"
    "Member Name\nCoach\nContact Number\nTier (1,2,3)\nJoin Date\n"
    "Member Mood\nSatisfaction Score"
)

# formula_compiler class.
PROMPT_STOCK_EFFECT_FORMULA = (
    'In the "Stock Movements" table, add a formula field called '
    '"Signed Quantity" that turns each movement into a signed number: '
    '"In" movements count as positive Quantity and "Out" movements as '
    "negative Quantity."
)


def _messages_text(output: EvalRunOutput) -> str:
    """Full formatted history as one string, for leaked-error substring checks."""

    return str(output.messages)


# ---------------------------------------------------------------------------
# Form for a table with a formula field
# ---------------------------------------------------------------------------


@register_scenario("prod-replay-form-for-table-with-formula-field")
def _form_for_table_with_formula_field_scenario(fx: Fixtures) -> EvalScenario:
    """Orders table whose formula field broke form-view creation in prod."""

    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(workspace=workspace, name="Orders DB")
    table = fx.create_database_table(database=database, name="Orders")
    fx.create_text_field(table=table, name="Customer", primary=True)
    price = fx.create_number_field(table=table, name="Price")
    fx.create_formula_field(
        table=table, name="Price incl. VAT", formula=f"field('{price.name}') * 1.21"
    )
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database, table),
        refs={"table": table},
    )


def _check_form_for_table_with_formula_field(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    """Prod: 'The field type formula is not compatible with the form view.'"""

    table = scenario.refs["table"]
    views = View.objects.filter(table=table)
    form_views = views.filter(content_type__model="formview")
    return [
        CheckResult(
            "form view created",
            form_views.exists(),
            hint=f"views: {[v.content_type.model for v in views]}",
        ),
    ]


register_case(
    EvalCase(
        id="prod-replay/form-for-table-with-formula-field",
        dataset="kuma-prod-replay",
        prompt=PROMPT_FORM_FOR_TABLE,
        scenario="prod-replay-form-for-table-with-formula-field",
        checks=_check_form_for_table_with_formula_field,
        max_iters=15,
        max_tool_errors=2,
        metadata={"failure_class": "view_config"},
    )
)


# ---------------------------------------------------------------------------
# Page inspection over existing builder elements
# ---------------------------------------------------------------------------


@register_scenario("prod-replay-page-inspection-existing-elements")
def _page_inspection_existing_elements_scenario(fx: Fixtures) -> EvalScenario:
    """Builder page with existing elements that ``list_elements`` choked on."""

    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    builder = fx.create_builder_application(
        user=user, workspace=workspace, name="Task App"
    )
    page = fx.create_builder_page(builder=builder, name="Tasks", path="/")
    fx.create_builder_heading_element(page=page, value="'Tasks'")
    fx.create_builder_text_element(page=page)
    fx.create_builder_button_element(page=page)
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_builder_ui_context(user, workspace, builder),
    )


def _check_page_inspection_existing_elements(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    """Prod: any page inspection died with `'XElement' has no attribute 'order'`."""

    # Inspecting is the model's call; the change is it can no longer kill the turn.
    return [
        CheckResult(
            "no attribute error leaked",
            "has no attribute" not in _messages_text(output),
            hint=f"tools called: {output.tool_calls}",
        ),
        CheckResult(
            "turn ended with a real answer",
            bool(output.answer.strip()),
            hint=f"answer: {output.answer[:200]!r}",
        ),
    ]


register_case(
    EvalCase(
        id="prod-replay/page-inspection-existing-elements",
        dataset="kuma-prod-replay",
        prompt=PROMPT_CHECKBOXES_NOT_ALIGNED,
        scenario="prod-replay-page-inspection-existing-elements",
        checks=_check_page_inspection_existing_elements,
        mode=AgentMode.APPLICATION,
        max_iters=15,
        max_tool_errors=2,
        metadata={"failure_class": "element_order"},
    )
)


# ---------------------------------------------------------------------------
# Project tracker onboarding
# ---------------------------------------------------------------------------


@register_scenario("prod-replay-project-tracker-onboarding")
def _project_tracker_onboarding_scenario(fx: Fixtures) -> EvalScenario:
    """Empty Project Tracker database, as the onboarding flow creates it."""

    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(
        workspace=workspace, name="Project Tracker"
    )
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database),
        refs={"database": database},
    )


def _check_project_tracker_onboarding(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    """Prod: 'Tool name conflicts with existing tool: create_rows_in_table_N'."""

    database = scenario.refs["database"]
    tables = list(Table.objects.filter(database=database))
    total_rows = sum(t.get_model().objects.count() for t in tables)
    return [
        CheckResult(
            "at least one table created",
            len(tables) >= 1,
            hint=f"tables: {[t.name for t in tables]}",
        ),
        CheckResult(
            "example rows created",
            total_rows > 0,
            hint=f"total rows: {total_rows}",
        ),
        CheckResult(
            "no tool name conflict leaked",
            "conflicts with existing tool" not in _messages_text(output),
            hint=f"tools called: {output.tool_calls}",
        ),
    ]


register_case(
    EvalCase(
        id="prod-replay/project-tracker-onboarding",
        dataset="kuma-prod-replay",
        prompt=PROMPT_PROJECT_TRACKER,
        scenario="prod-replay-project-tracker-onboarding",
        checks=_check_project_tracker_onboarding,
        max_iters=30,
        max_tool_errors=3,
        metadata={"failure_class": "row_tool_conflict"},
    )
)


# ---------------------------------------------------------------------------
# ISO week number formula
# ---------------------------------------------------------------------------


@register_scenario("prod-replay-iso-week-number-formula")
def _iso_week_number_formula_scenario(fx: Fixtures) -> EvalScenario:
    """Records table with the {Recorded Date} column the prompt references."""

    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(workspace=workspace, name="Tracking DB")
    table = fx.create_database_table(database=database, name="Records")
    fx.create_text_field(table=table, name="Name", primary=True)
    fx.create_date_field(table=table, name="Recorded Date")
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database, table),
        refs={"table": table},
    )


def _check_iso_week_number_formula(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    """Prod: 'Exceeded maximum output retries (1)' from the formula agent."""

    table = scenario.refs["table"]
    all_formula_fields = list(FormulaField.objects.filter(table=table))
    week_fields = [f for f in all_formula_fields if "week" in f.name.lower()]
    return [
        CheckResult(
            "week number formula field created",
            len(week_fields) >= 1,
            hint=f"formula fields: {[f.name for f in all_formula_fields]}",
        ),
        CheckResult(
            "formula is valid",
            bool(week_fields) and not week_fields[0].error,
            hint=f"error: {week_fields[0].error if week_fields else 'no field'}",
        ),
    ]


register_case(
    EvalCase(
        id="prod-replay/iso-week-number-formula",
        dataset="kuma-prod-replay",
        prompt=PROMPT_ISO_WEEK_FORMULA,
        scenario="prod-replay-iso-week-number-formula",
        checks=_check_iso_week_number_formula,
        max_iters=15,
        max_tool_errors=2,
        metadata={"failure_class": "formula_agent_retries"},
    )
)


# ---------------------------------------------------------------------------
# Impossible formula request
# ---------------------------------------------------------------------------


@register_scenario("prod-replay-impossible-formula-request")
def _impossible_formula_request_scenario(fx: Fixtures) -> EvalScenario:
    """Products table with the URL field the impossible request points at."""

    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(workspace=workspace, name="Products DB")
    table = fx.create_database_table(database=database, name="Products")
    fx.create_text_field(table=table, name="Name", primary=True)
    fx.create_url_field(table=table, name="Product Page URL")
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database, table),
        refs={"table": table},
    )


def _check_impossible_formula_request(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    """Prod: same retries exhaustion when the request cannot be expressed."""

    # The exhaustion may appear in a contained retry prompt; surviving it is the fix.
    return [
        CheckResult(
            "turn ended with a real answer",
            bool(output.answer.strip()),
            hint=f"answer: {output.answer[:200]!r}",
        ),
    ]


register_case(
    EvalCase(
        id="prod-replay/impossible-formula-request",
        dataset="kuma-prod-replay",
        prompt=PROMPT_IMPOSSIBLE_FORMULA,
        scenario="prod-replay-impossible-formula-request",
        checks=_check_impossible_formula_request,
        max_iters=15,
        max_tool_errors=3,
        metadata={"failure_class": "formula_agent_retries"},
    )
)


# ---------------------------------------------------------------------------
# Fake rows into typed fields
# ---------------------------------------------------------------------------


@register_scenario("prod-replay-fake-rows-into-typed-fields")
def _fake_rows_into_typed_fields_scenario(fx: Fixtures) -> EvalScenario:
    """Members table with the exact typed fields the prompt enumerates."""

    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(workspace=workspace, name="Gym DB")
    table = fx.create_database_table(database=database, name="Members")
    fx.create_text_field(table=table, name="Member Name", primary=True)
    fx.create_text_field(table=table, name="Coach")
    fx.create_text_field(table=table, name="Contact Number")
    tier = fx.create_single_select_field(table=table, name="Tier")
    for value in ("1", "2", "3"):
        fx.create_select_option(field=tier, value=value)
    fx.create_date_field(table=table, name="Join Date")
    fx.create_text_field(table=table, name="Member Mood")
    fx.create_number_field(table=table, name="Satisfaction Score")
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database, table),
        refs={"table": table},
    )


def _check_fake_rows_into_typed_fields(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    """Prod: 'value must be a decimal number' / date format errors ended the turn."""

    table = scenario.refs["table"]
    row_count = table.get_model().objects.count()
    return [
        CheckResult(
            "rows were created",
            row_count > 0,
            hint=f"rows: {row_count}",
        ),
    ]


register_case(
    EvalCase(
        id="prod-replay/fake-rows-into-typed-fields",
        dataset="kuma-prod-replay",
        prompt=PROMPT_FAKE_MEMBER_ROWS,
        scenario="prod-replay-fake-rows-into-typed-fields",
        checks=_check_fake_rows_into_typed_fields,
        max_iters=20,
        max_tool_errors=3,
        metadata={"failure_class": "row_validation"},
    )
)


# ---------------------------------------------------------------------------
# Signed stock effect formula
# ---------------------------------------------------------------------------


@register_scenario("prod-replay-signed-stock-effect-formula")
def _signed_stock_effect_formula_scenario(fx: Fixtures) -> EvalScenario:
    """Stock Movements table with the Movement Type/Quantity fields it needs."""

    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(workspace=workspace, name="Inventory DB")
    table = fx.create_database_table(database=database, name="Stock Movements")
    fx.create_text_field(table=table, name="Reference", primary=True)
    movement = fx.create_single_select_field(table=table, name="Movement Type")
    for value in ("In", "Out"):
        fx.create_select_option(field=movement, value=value)
    fx.create_number_field(table=table, name="Quantity")
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database, table),
        refs={"table": table},
    )


def _check_signed_stock_effect_formula(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    """Prod: bare formula compiler errors ('and'/'or' arity) ended the turn."""

    table = scenario.refs["table"]
    # The crash class is what this replay verifies; the exact field name is not.
    formula_fields = list(FormulaField.objects.filter(table=table))
    return [
        CheckResult(
            "a formula field was created",
            len(formula_fields) >= 1,
            hint=f"formula fields: {[f.name for f in formula_fields]}",
        ),
        CheckResult(
            "formula is valid",
            bool(formula_fields) and not formula_fields[0].error,
            hint=f"error: {formula_fields[0].error if formula_fields else 'no field'}",
        ),
    ]


register_case(
    EvalCase(
        id="prod-replay/signed-stock-effect-formula",
        dataset="kuma-prod-replay",
        prompt=PROMPT_STOCK_EFFECT_FORMULA,
        scenario="prod-replay-signed-stock-effect-formula",
        checks=_check_signed_stock_effect_formula,
        max_iters=15,
        max_tool_errors=2,
        metadata={"failure_class": "formula_compiler"},
    )
)
