import pytest

from baserow.contrib.database.rows.handler import RowHandler

from .eval_utils import (
    EvalChecklist,
    build_database_ui_context,
    count_tool_errors,
    create_eval_assistant,
    print_message_history,
)

# ---------------------------------------------------------------------------
# Eval prompts — one per test, easy to scan for coverage
# ---------------------------------------------------------------------------

PROMPT_CREATES_ROWS_WITH_ALL_FIELD_TYPES = (
    "Create 5 rows with diverse sample data in table {table_name}. "
    "Fill in ALL fields with realistic values."
)


def _create_rich_table(data_fixture):
    """
    Create a table with all managed field types plus a linked table
    with sample data.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    # Linked table (target for link_row fields)
    linked_table = data_fixture.create_database_table(
        database=database, name="Categories"
    )
    linked_primary = data_fixture.create_text_field(
        table=linked_table, name="Name", primary=True
    )

    # Populate linked table with sample rows
    RowHandler().force_create_rows(
        user,
        linked_table,
        [
            {linked_primary.db_column: "Work"},
            {linked_primary.db_column: "Personal"},
            {linked_primary.db_column: "Urgent"},
        ],
    )

    # Main table with all managed field types
    table = data_fixture.create_database_table(database=database, name="Tasks")
    title = data_fixture.create_text_field(table=table, name="Title", primary=True)
    description = data_fixture.create_long_text_field(table=table, name="Description")
    estimated_hours = data_fixture.create_number_field(
        table=table, name="Estimated Hours", number_decimal_places=1
    )
    completed = data_fixture.create_boolean_field(table=table, name="Completed")
    due_date = data_fixture.create_date_field(table=table, name="Due Date")
    created_at = data_fixture.create_date_field(
        table=table, name="Created At", date_include_time=True
    )

    status_field = data_fixture.create_single_select_field(table=table, name="Status")
    data_fixture.create_select_option(field=status_field, value="To Do", order=0)
    data_fixture.create_select_option(field=status_field, value="In Progress", order=1)
    data_fixture.create_select_option(field=status_field, value="Done", order=2)

    tags_field = data_fixture.create_multiple_select_field(table=table, name="Tags")
    data_fixture.create_select_option(field=tags_field, value="Bug", order=0)
    data_fixture.create_select_option(field=tags_field, value="Feature", order=1)
    data_fixture.create_select_option(field=tags_field, value="Docs", order=2)

    category_field = data_fixture.create_link_row_field(
        table=table,
        link_row_table=linked_table,
        name="Category",
        link_row_multiple_relationships=False,
    )
    related_categories_field = data_fixture.create_link_row_field(
        table=table,
        link_row_table=linked_table,
        name="Related Categories",
        link_row_multiple_relationships=True,
    )

    return {
        "user": user,
        "workspace": workspace,
        "database": database,
        "table": table,
        "linked_table": linked_table,
        "fields": {
            "title": title,
            "description": description,
            "estimated_hours": estimated_hours,
            "completed": completed,
            "due_date": due_date,
            "created_at": created_at,
            "status": status_field,
            "tags": tags_field,
            "category": category_field,
            "related_categories": related_categories_field,
        },
    }


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_creates_rows_with_all_field_types(data_fixture, eval_model, db):
    """
    Agent should create rows with sensible data for every field type.

    This tests the full flow:
    1. Agent calls get_tables_schema to learn the table structure
    2. Agent calls load_row_tools to unlock create_rows_in_table_X
    3. Agent calls create_rows_in_table_X with all fields populated
    """

    res = _create_rich_table(data_fixture)
    user = res["user"]
    workspace = res["workspace"]
    database = res["database"]
    table = res["table"]
    fields = res["fields"]

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=20, model=eval_model
    )
    ui_context = build_database_ui_context(user, workspace, database, table=table)
    deps.tool_helpers.request_context["ui_context"] = ui_context

    result = agent.run_sync(
        user_prompt=PROMPT_CREATES_ROWS_WITH_ALL_FIELD_TYPES.format(
            table_name=table.name
        ),
        deps=deps,
        model=model,
        usage_limits=usage_limits,
        toolsets=[toolset],
    )

    print_message_history(result)
    err_count, err_hint = count_tool_errors(result)

    table_model = table.get_model()
    row_count = table_model.objects.count()
    sample_rows = list(table_model.objects.all())

    def _get_field_value(row, field_name):
        return getattr(row, fields[field_name].db_column, None)

    def _any_row(check_fn):
        return any(check_fn(r) for r in sample_rows)

    with EvalChecklist("creates rows with all field types") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check("5 rows created", row_count == 5, hint=f"got {row_count}")
        checks.check(
            "title populated",
            _any_row(lambda r: bool(_get_field_value(r, "title"))),
        )
        checks.check(
            "description populated",
            _any_row(lambda r: bool(_get_field_value(r, "description"))),
        )
        checks.check(
            "estimated_hours populated",
            _any_row(lambda r: _get_field_value(r, "estimated_hours") is not None),
        )
        checks.check(
            "estimated_hours > 0 in at least one row",
            _any_row(lambda r: (_get_field_value(r, "estimated_hours") or 0) > 0),
        )
        checks.check(
            "completed has at least one True",
            _any_row(lambda r: _get_field_value(r, "completed") is True),
        )
        checks.check(
            "due_date populated",
            _any_row(lambda r: _get_field_value(r, "due_date") is not None),
        )
        checks.check(
            "created_at populated",
            _any_row(lambda r: _get_field_value(r, "created_at") is not None),
        )
        checks.check(
            "status is a known option",
            _any_row(
                lambda r: bool(_get_field_value(r, "status"))
                and _get_field_value(r, "status").value
                in ["To Do", "In Progress", "Done"]
            ),
        )
        checks.check(
            "tags has at least one known option",
            _any_row(
                lambda r: bool(
                    set(_get_field_value(r, "tags").values_list("value", flat=True))
                    & {"Bug", "Feature", "Docs"}
                )
            ),
        )
        checks.check(
            "category linked",
            _any_row(lambda r: len(_get_field_value(r, "category").all()) > 0),
        )
        checks.check(
            "related_categories linked",
            _any_row(
                lambda r: len(_get_field_value(r, "related_categories").all()) > 0
            ),
        )
