"""
Agent-level evals for the database assistant.

These run the full agent loop with real tools and the production system prompt.
They verify:
- The agent can create tables with appropriate fields
- Field types and configurations are correct
- No tool errors in the trajectory
- Message history is captured for inspection

Run with: pytest -m eval -k test_eval_agent_database -v -s

Configuration (via environment variables):
- EVAL_LLM_MODEL: The model to use (default: "groq:openai/gpt-oss-120b")
- OPENAI_API_KEY: Required for OpenAI models
- GROQ_API_KEY: Required for Groq models
"""

import pytest

from baserow.contrib.database.fields.models import (
    BooleanField,
    DateField,
    LinkRowField,
    LongTextField,
    NumberField,
    SingleSelectField,
    TextField,
)
from baserow.contrib.database.models import Table
from baserow.contrib.database.views.models import View, ViewFilter
from baserow.core.db import specific_iterator

from .eval_utils import (
    assert_no_tool_errors,
    build_database_ui_context,
    create_eval_assistant,
    format_message_history,
    print_message_history,
)

# ---------------------------------------------------------------------------
# Eval prompts — one per test, easy to scan for coverage
# ---------------------------------------------------------------------------

PROMPT_CREATES_SIMPLE_TABLE = (
    "Create a Recipes table in database {database_name} with these fields: "
    "Name, Description, Prep Time in Minutes, Servings, and Vegetarian. "
    "Don't add sample rows."
)

PROMPT_CREATES_TABLE_WITH_SELECT_FIELDS = (
    "Create a Tasks table in database {database_name} with: "
    "Title, Status with options: To Do, In Progress, Done, "
    "Priority with options: Low, Medium, High, "
    "and Due Date. Don't add sample rows."
)

PROMPT_CREATES_RELATED_TABLES = (
    "Create a simple project management system in database {database_name} with: "
    "1. A Projects table with Name and Description. "
    "2. A Tasks table with Title, Status with options: To Do, In Progress, Done, "
    "and a link to the Projects table. "
    "Don't add sample rows."
)

PROMPT_CREATES_DATABASE_FROM_DESCRIPTION = (
    "Set up a Bookstore database to manage a bookstore. "
    "I need tables for Books and Authors. "
    "Books should have title, description, price, publication date, and a link to Authors. "
    "Authors should have name and bio. "
    "Don't add sample rows."
)

PROMPT_MESSAGE_HISTORY_CONTAINS_TOOL_CALLS = (
    "List all tables in database {database_id}."
)


def _run_agent(
    agent, deps, tracker, model, usage_limits, toolset, question, ui_context
):
    """Helper to run the agent with standard configuration."""
    deps.tool_helpers.request_context["ui_context"] = ui_context

    result = agent.run_sync(
        user_prompt=question,
        deps=deps,
        model=model,
        usage_limits=usage_limits,
        toolsets=[toolset],
    )
    return result


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_creates_simple_table(data_fixture, eval_model):
    """Agent should create a table with basic field types when asked."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(
        workspace=workspace, name="Recipe Database"
    )

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=15, model=eval_model
    )
    ui_context = build_database_ui_context(user, workspace, database)

    result = _run_agent(
        agent,
        deps,
        tracker,
        model,
        usage_limits,
        toolset,
        question=PROMPT_CREATES_SIMPLE_TABLE.format(database_name=database.name),
        ui_context=ui_context,
    )

    # Print message history for inspection
    print_message_history(result)
    history = format_message_history(result)

    # Verify tool calls happened
    tool_calls = [e for e in history if e.get("tool_name") and e["role"] == "assistant"]
    assert len(tool_calls) > 0, "Agent should have made at least one tool call"

    # Verify no tool errors
    assert_no_tool_errors(tracker, result)

    # Verify the table was created
    tables = Table.objects.filter(database=database)
    recipe_tables = [t for t in tables if "recipe" in t.name.lower()]
    assert len(recipe_tables) == 1, (
        f"Expected 1 Recipes table, got {len(recipe_tables)}: "
        f"{[t.name for t in tables]}"
    )

    table = recipe_tables[0]
    fields = specific_iterator(table.field_set.all())

    # Check field types exist
    field_names = {f.name.lower(): f for f in fields}

    assert any("name" in name for name in field_names), (
        f"Missing 'Name' field. Fields: {list(field_names.keys())}"
    )
    assert any("description" in name for name in field_names), (
        f"Missing 'Description' field. Fields: {list(field_names.keys())}"
    )

    # Verify field types
    text_fields = [f for f in fields if isinstance(f, (TextField, LongTextField))]
    assert len(text_fields) >= 2, (
        f"Expected at least 2 text/long_text fields, got {len(text_fields)}"
    )

    number_fields = [f for f in fields if isinstance(f, NumberField)]
    assert len(number_fields) >= 2, (
        f"Expected at least 2 number fields, got {len(number_fields)}"
    )

    boolean_fields = [f for f in fields if isinstance(f, BooleanField)]
    assert len(boolean_fields) >= 1, (
        f"Expected at least 1 boolean field, got {len(boolean_fields)}"
    )


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_creates_table_with_select_fields(data_fixture, eval_model):
    """Agent should create a table with single select and appropriate options."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(
        workspace=workspace, name="Task Management"
    )

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=15, model=eval_model
    )
    ui_context = build_database_ui_context(user, workspace, database)

    result = _run_agent(
        agent,
        deps,
        tracker,
        model,
        usage_limits,
        toolset,
        question=PROMPT_CREATES_TABLE_WITH_SELECT_FIELDS.format(
            database_name=database.name
        ),
        ui_context=ui_context,
    )

    print_message_history(result)
    assert_no_tool_errors(tracker, result)

    # Verify the table was created
    tables = Table.objects.filter(database=database)
    task_tables = [t for t in tables if "task" in t.name.lower()]
    assert len(task_tables) == 1, (
        f"Expected 1 Tasks table, got {len(task_tables)}: {[t.name for t in tables]}"
    )

    table = task_tables[0]
    fields = specific_iterator(table.field_set.all())

    # Verify select fields exist with options
    select_fields = [f for f in fields if isinstance(f, SingleSelectField)]
    assert len(select_fields) >= 2, (
        f"Expected at least 2 single select fields (Status, Priority), "
        f"got {len(select_fields)}: {[f.name for f in select_fields]}"
    )

    # Check Status field has options
    status_field = next((f for f in select_fields if "status" in f.name.lower()), None)
    assert status_field is not None, (
        f"Missing 'Status' select field. Select fields: "
        f"{[f.name for f in select_fields]}"
    )
    status_options = list(status_field.select_options.values_list("value", flat=True))
    assert len(status_options) >= 3, (
        f"Status field should have at least 3 options, got: {status_options}"
    )

    # Check date field
    date_fields = [f for f in fields if isinstance(f, DateField)]
    assert len(date_fields) >= 1, (
        f"Expected at least 1 date field, got {len(date_fields)}"
    )


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_creates_related_tables(data_fixture, eval_model):
    """Agent should create multiple tables with link_row relationships."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(
        workspace=workspace, name="Project Management"
    )

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=20, model=eval_model
    )
    ui_context = build_database_ui_context(user, workspace, database)

    result = _run_agent(
        agent,
        deps,
        tracker,
        model,
        usage_limits,
        toolset,
        question=PROMPT_CREATES_RELATED_TABLES.format(database_name=database.name),
        ui_context=ui_context,
    )

    print_message_history(result)
    assert_no_tool_errors(tracker, result)

    tables = Table.objects.filter(database=database)
    table_names = {t.name.lower(): t for t in tables}

    # Verify both tables were created
    project_tables = [name for name in table_names if "project" in name]
    task_tables = [name for name in table_names if "task" in name]

    assert len(project_tables) >= 1, (
        f"Expected a Projects table, got tables: {list(table_names.keys())}"
    )
    assert len(task_tables) >= 1, (
        f"Expected a Tasks table, got tables: {list(table_names.keys())}"
    )

    # Verify link_row field exists
    task_table = table_names[task_tables[0]]
    task_fields = specific_iterator(task_table.field_set.all())
    link_fields = [f for f in task_fields if isinstance(f, LinkRowField)]
    assert len(link_fields) >= 1, (
        f"Expected at least 1 link_row field in Tasks, got {len(link_fields)}. "
        f"Fields: {[(f.name, type(f).__name__) for f in task_fields]}"
    )

    # The link field should point to the projects table
    project_table = table_names[project_tables[0]]
    link_to_projects = [
        f for f in link_fields if f.link_row_table_id == project_table.id
    ]
    assert len(link_to_projects) >= 1, (
        f"Expected a link_row field pointing to Projects table (id={project_table.id}), "
        f"got links to: {[(f.name, f.link_row_table_id) for f in link_fields]}"
    )


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_creates_database_from_description(data_fixture, eval_model):
    """
    Agent should create a full database structure from a high-level description.

    This tests the agent's ability to interpret a vague request and create
    appropriate tables, fields, and relationships.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=25, model=eval_model
    )
    ui_context = build_database_ui_context(user, workspace)

    result = _run_agent(
        agent,
        deps,
        tracker,
        model,
        usage_limits,
        toolset,
        question=PROMPT_CREATES_DATABASE_FROM_DESCRIPTION,
        ui_context=ui_context,
    )

    print_message_history(result)
    assert_no_tool_errors(tracker, result)

    from baserow.contrib.database.models import Database

    databases = Database.objects.filter(workspace=workspace)
    assert databases.exists(), "Agent should have created a database in the workspace"
    tables = Table.objects.filter(database__in=databases)
    table_names_lower = [t.name.lower() for t in tables]

    # Verify core tables were created
    assert any("book" in name for name in table_names_lower), (
        f"Expected a Books table, got: {[t.name for t in tables]}"
    )
    assert any("author" in name for name in table_names_lower), (
        f"Expected an Authors table, got: {[t.name for t in tables]}"
    )

    # Verify Books table has expected field types
    books_table = next(t for t in tables if "book" in t.name.lower())
    books_fields = specific_iterator(books_table.field_set.all())
    books_field_types = {type(f).__name__ for f in books_fields}

    assert TextField in {type(f) for f in books_fields} or LongTextField in {
        type(f) for f in books_fields
    }, f"Books should have text fields. Field types: {books_field_types}"

    assert NumberField in {type(f) for f in books_fields}, (
        f"Books should have a number field (price). Field types: {books_field_types}"
    )

    assert DateField in {type(f) for f in books_fields}, (
        f"Books should have a date field. Field types: {books_field_types}"
    )

    assert LinkRowField in {type(f) for f in books_fields}, (
        f"Books should have a link_row field to Authors. "
        f"Field types: {books_field_types}"
    )


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_message_history_contains_tool_calls(data_fixture, eval_model):
    """
    Verify that message history captures tool calls with arguments and results.

    This is a meta-eval: it verifies the message history inspection works,
    so we can use it to debug schema/tool-calling issues.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=10, model=eval_model
    )
    ui_context = build_database_ui_context(user, workspace, database)

    result = _run_agent(
        agent,
        deps,
        tracker,
        model,
        usage_limits,
        toolset,
        question=PROMPT_MESSAGE_HISTORY_CONTAINS_TOOL_CALLS.format(
            database_id=database.id
        ),
        ui_context=ui_context,
    )

    print_message_history(result)
    history = format_message_history(result)

    # Should have at least: system prompt, user message, assistant response
    assert len(history) >= 2, (
        f"Expected at least 2 messages in history, got {len(history)}"
    )

    # Verify we can find tool call entries
    tool_call_entries = [
        e for e in history if e.get("tool_name") and e["role"] == "assistant"
    ]

    # The agent should call list_tables
    tool_names_called = {e["tool_name"] for e in tool_call_entries}
    assert "list_tables" in tool_names_called, (
        f"Expected agent to call 'list_tables', but called: {tool_names_called}"
    )

    # Verify tool call has arguments
    list_tables_call = next(
        e for e in tool_call_entries if e["tool_name"] == "list_tables"
    )
    assert "args" in list_tables_call, (
        "Tool call should have 'args' in the message history"
    )

    # Verify tool result entries exist
    tool_result_entries = [
        e
        for e in history
        if e.get("tool_name") and e["role"] == "user" and "Return" in e.get("type", "")
    ]
    assert len(tool_result_entries) >= 1, (
        f"Expected at least 1 tool result in history. "
        f"User entries: {[e.get('type') for e in history if e['role'] == 'user']}"
    )


# ---------------------------------------------------------------------------
# Parametrized view creation eval
# ---------------------------------------------------------------------------


def _setup_grid(data_fixture, table):
    """Grid view needs no special fields."""
    return {}


def _setup_kanban(data_fixture, table):
    """Kanban needs a single_select field."""
    field = data_fixture.create_single_select_field(table=table, name="Status")
    data_fixture.create_select_option(field=field, value="To Do", order=1)
    data_fixture.create_select_option(field=field, value="In Progress", order=2)
    data_fixture.create_select_option(field=field, value="Done", order=3)
    return {"status_field": field}


def _setup_calendar(data_fixture, table):
    """Calendar needs a date field."""
    field = data_fixture.create_date_field(table=table, name="Due Date")
    return {"date_field": field}


def _setup_gallery(data_fixture, table):
    """Gallery needs a file field."""
    field = data_fixture.create_file_field(table=table, name="Cover Image")
    return {"file_field": field}


def _setup_timeline(data_fixture, table):
    """Timeline needs two date fields with matching include_time."""
    start = data_fixture.create_date_field(
        table=table, name="Start Date", date_include_time=False
    )
    end = data_fixture.create_date_field(
        table=table, name="End Date", date_include_time=False
    )
    return {"start_field": start, "end_field": end}


def _setup_form(data_fixture, table):
    """Form view uses existing fields; no extra setup beyond what's already there."""
    return {}


_VIEW_TEST_CASES = [
    pytest.param(
        "grid",
        _setup_grid,
        "Create a grid view called 'All Tasks' for table {table_name}.",
        id="grid",
    ),
    pytest.param(
        "kanban",
        _setup_kanban,
        (
            "Create a kanban view called 'Task Board' for table {table_name}. "
            "Use the Status field (id: {status_field_name}) as the column field."
        ),
        id="kanban",
    ),
    pytest.param(
        "calendar",
        _setup_calendar,
        (
            "Create a calendar view called 'Schedule' for table {table_name}. "
            "Use the Due Date field (id: {date_field_name}) as the date field."
        ),
        id="calendar",
    ),
    pytest.param(
        "gallery",
        _setup_gallery,
        (
            "Create a gallery view called 'Image Gallery' for table {table_name}. "
            "Use the Cover Image field (id: {file_field_name}) as the cover image."
        ),
        id="gallery",
    ),
    pytest.param(
        "timeline",
        _setup_timeline,
        (
            "Create a timeline view called 'Project Timeline' for table {table_name}. "
            "Use Start Date (id: {start_field_name}) and End Date (id: {end_field_name})."
        ),
        id="timeline",
    ),
    pytest.param(
        "form",
        _setup_form,
        (
            "Create a form view called 'Submit Task' for table {table_name}. "
            "Include the Name field in the form."
        ),
        id="form",
    ),
]


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("view_type,setup_fn,prompt_template", _VIEW_TEST_CASES)
def test_agent_creates_view(
    data_fixture, eval_model, view_type, setup_fn, prompt_template
):
    """Agent should create a view of the given type without tool errors."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Tasks")
    data_fixture.create_text_field(table=table, name="Name", primary=True)

    # Set up type-specific fields
    extra = setup_fn(data_fixture, table)

    # Build prompt with field IDs injected
    fmt_kwargs = {"table_name": table.name}
    for key, field in extra.items():
        fmt_kwargs[f"{key}_name"] = field.name
    prompt = prompt_template.format(**fmt_kwargs)

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=15, model=eval_model
    )
    ui_context = build_database_ui_context(user, workspace, database, table)

    result = _run_agent(
        agent,
        deps,
        tracker,
        model,
        usage_limits,
        toolset,
        question=prompt,
        ui_context=ui_context,
    )

    print_message_history(result)
    assert_no_tool_errors(tracker, result)

    # Verify a view of the expected type was created (excluding the default grid view)
    views = View.objects.filter(table=table)
    typed_views = [
        v for v in views if v.get_type().type == view_type and v.name != "Grid"
    ]
    assert len(typed_views) >= 1, (
        f"Expected at least 1 {view_type} view (besides the default 'Grid'), "
        f"got views: {[(v.name, v.get_type().type) for v in views]}"
    )


# ---------------------------------------------------------------------------
# Parametrized view filter creation eval
# ---------------------------------------------------------------------------


def _setup_text_filter(data_fixture, table):
    field = data_fixture.create_text_field(table=table, name="Description")
    return {"text_field": field}


def _setup_number_filter(data_fixture, table):
    field = data_fixture.create_number_field(table=table, name="Amount")
    return {"number_field": field}


def _setup_date_filter(data_fixture, table):
    field = data_fixture.create_date_field(table=table, name="Due Date")
    return {"date_field": field}


def _setup_single_select_filter(data_fixture, table):
    field = data_fixture.create_single_select_field(table=table, name="Status")
    data_fixture.create_select_option(field=field, value="Active", order=1)
    data_fixture.create_select_option(field=field, value="Pending", order=2)
    data_fixture.create_select_option(field=field, value="Closed", order=3)
    return {"select_field": field}


def _setup_multiple_select_filter(data_fixture, table):
    field = data_fixture.create_multiple_select_field(table=table, name="Tags")
    data_fixture.create_select_option(field=field, value="Important", order=1)
    data_fixture.create_select_option(field=field, value="Urgent", order=2)
    data_fixture.create_select_option(field=field, value="Low", order=3)
    return {"multi_field": field}


def _setup_boolean_filter(data_fixture, table):
    field = data_fixture.create_boolean_field(table=table, name="Active")
    return {"bool_field": field}


_FILTER_TEST_CASES = [
    pytest.param(
        "text",
        _setup_text_filter,
        (
            "Create a grid view called 'Filtered' for table {table_name}, "
            "then add a filter on the Description field (id: {text_field_name}) "
            "to only show rows where it contains 'important'."
        ),
        "contains",
        id="text_contains",
    ),
    pytest.param(
        "number",
        _setup_number_filter,
        (
            "Create a grid view called 'Filtered' for table {table_name}, "
            "then add a filter on the Amount field (id: {number_field_name}) "
            "to only show rows where it is higher than 100."
        ),
        "higher_than",
        id="number_higher_than",
    ),
    pytest.param(
        "date",
        _setup_date_filter,
        (
            "Create a grid view called 'Filtered' for table {table_name}, "
            "then add a filter on the Due Date field (id: {date_field_name}) "
            "to only show rows where the date is after today."
        ),
        "date_is_after",
        id="date_after",
    ),
    pytest.param(
        "single_select",
        _setup_single_select_filter,
        (
            "Create a grid view called 'Filtered' for table {table_name}, "
            "then add a filter on the Status field (id: {select_field_name}) "
            "to only show rows where Status is any of 'Active' or 'Pending'."
        ),
        "single_select_is_any_of",
        id="single_select_is_any_of",
    ),
    pytest.param(
        "multiple_select",
        _setup_multiple_select_filter,
        (
            "Create a grid view called 'Filtered' for table {table_name}, "
            "then add a filter on the Tags field (id: {multi_field_name}) "
            "to only show rows where Tags has 'Important'."
        ),
        "multiple_select_has",
        id="multiple_select_has",
    ),
    pytest.param(
        "boolean",
        _setup_boolean_filter,
        (
            "Create a grid view called 'Filtered' for table {table_name}, "
            "then add a filter on the Active field (id: {bool_field_name}) "
            "to only show rows where Active is true."
        ),
        "boolean",
        id="boolean_is",
    ),
]


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "filter_type,setup_fn,prompt_template,expected_orm_type", _FILTER_TEST_CASES
)
def test_agent_creates_view_filter(
    data_fixture, eval_model, filter_type, setup_fn, prompt_template, expected_orm_type
):
    """Agent should create a view with the correct filter type without tool errors."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Tasks")
    data_fixture.create_text_field(table=table, name="Name", primary=True)

    # Set up type-specific fields
    extra = setup_fn(data_fixture, table)

    # Build prompt with field IDs injected
    fmt_kwargs = {"table_name": table.name}
    for key, field in extra.items():
        fmt_kwargs[f"{key}_name"] = field.name
    prompt = prompt_template.format(**fmt_kwargs)

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=15, model=eval_model
    )
    ui_context = build_database_ui_context(user, workspace, database, table)

    result = _run_agent(
        agent,
        deps,
        tracker,
        model,
        usage_limits,
        toolset,
        question=prompt,
        ui_context=ui_context,
    )

    print_message_history(result)
    assert_no_tool_errors(tracker, result)

    # Verify a view filter of the expected ORM type was created
    filters = ViewFilter.objects.filter(view__table=table, type=expected_orm_type)
    assert filters.exists(), (
        f"Expected a ViewFilter with type='{expected_orm_type}', "
        f"got: {list(ViewFilter.objects.filter(view__table=table).values_list('type', flat=True))}"
    )
