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
    EvalChecklist,
    build_database_ui_context,
    count_tool_errors,
    create_eval_assistant,
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

PROMPT_CREATE_RELATED_TABLES_WITH_SAMPLE_ROWS = (
    "Set up the Bookstore database {database_name} with: "
    "1. An Authors table with Name and Bio. "
    "2. A Books table with Title, Genre "
    "(single select: Fiction, Non-Fiction, Science, History), "
    "Price, and a link to the Authors table."
)

# -- View creation prompts --------------------------------------------------

PROMPT_CREATE_GRID_VIEW = (
    "Create a grid view called 'All Tasks' for table {table_name}."
)

PROMPT_CREATE_KANBAN_VIEW = (
    "Create a kanban view called 'Task Board' for table {table_name}. "
    "Use the Status field (id: {status_field_name}) as the column field."
)

PROMPT_CREATE_CALENDAR_VIEW = (
    "Create a calendar view called 'Schedule' for table {table_name}. "
    "Use the Due Date field (id: {date_field_name}) as the date field."
)

PROMPT_CREATE_GALLERY_VIEW = (
    "Create a gallery view called 'Image Gallery' for table {table_name}. "
    "Use the Cover Image field (id: {file_field_name}) as the cover image."
)

PROMPT_CREATE_TIMELINE_VIEW = (
    "Create a timeline view called 'Project Timeline' for table {table_name}. "
    "Use Start Date (id: {start_field_name}) and End Date (id: {end_field_name})."
)

PROMPT_CREATE_FORM_VIEW = (
    "Create a form view called 'Submit Task' for table {table_name}. "
    "Include the Name field in the form."
)

# -- View filter prompts ----------------------------------------------------

PROMPT_FILTER_TEXT_CONTAINS = (
    "Create a grid view called 'Filtered' for table {table_name}, "
    "then add a filter on the Description field (id: {text_field_name}) "
    "to only show rows where it contains 'important'."
)

PROMPT_FILTER_NUMBER_GREATER_THAN = (
    "Create a grid view called 'Filtered' for table {table_name}, "
    "then add a filter on the Amount field (id: {number_field_name}) "
    "to only show rows where it is greater than 100."
)

PROMPT_FILTER_DATE_AFTER = (
    "Create a grid view called 'Filtered' for table {table_name}, "
    "then add a filter on the Due Date field (id: {date_field_name}) "
    "to only show rows where the date is after today."
)

PROMPT_FILTER_SINGLE_SELECT_ANY_OF = (
    "Create a grid view called 'Filtered' for table {table_name}, "
    "then add a filter on the Status field (id: {select_field_name}) "
    "to only show rows where Status is any of 'Active' or 'Pending'."
)

PROMPT_FILTER_MULTIPLE_SELECT_HAS = (
    "Create a grid view called 'Filtered' for table {table_name}, "
    "then add a filter on the Tags field (id: {multi_field_name}) "
    "to only show rows where Tags has 'Important'."
)

PROMPT_FILTER_BOOLEAN_IS = (
    "Create a grid view called 'Filtered' for table {table_name}, "
    "then add a filter on the Active field (id: {bool_field_name}) "
    "to only show rows where Active is true."
)

# -- Field update/delete prompts --------------------------------------------

PROMPT_UPDATE_FIELD_RENAME = (
    "Rename the Description field to Summary in the {table_name} table."
)

PROMPT_UPDATE_FIELD_SELECT_OPTIONS = (
    "Add an 'In Progress' option to the Status field in the {table_name} table."
)

PROMPT_DELETE_FIELD = "Delete the Notes field from the {table_name} table."


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

    print_message_history(result)
    err_count, err_hint = count_tool_errors(result)

    tables = Table.objects.filter(database=database)
    recipe_tables = [t for t in tables if "recipe" in t.name.lower()]
    table = recipe_tables[0] if recipe_tables else None
    fields = list(specific_iterator(table.field_set.all())) if table else []
    field_names = {f.name.lower(): f for f in fields}
    text_fields = [f for f in fields if isinstance(f, (TextField, LongTextField))]
    number_fields = [f for f in fields if isinstance(f, NumberField)]
    boolean_fields = [f for f in fields if isinstance(f, BooleanField)]

    prep_number = next(
        (
            f
            for f in number_fields
            if any(kw in f.name.lower() for kw in ("prep", "time", "minute"))
        ),
        None,
    )
    veg_bool = next((f for f in boolean_fields if "vegetarian" in f.name.lower()), None)

    with EvalChecklist("creates Recipes table") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check(
            "Recipes table created",
            len(recipe_tables) == 1,
            hint=f"got {len(recipe_tables)}: {[t.name for t in tables]}",
        )
        checks.check(
            "Name field exists",
            any("name" in n for n in field_names),
            hint=f"fields: {list(field_names.keys())}",
        )
        checks.check(
            "Description field exists",
            any("description" in n for n in field_names),
            hint=f"fields: {list(field_names.keys())}",
        )
        checks.check(
            ">=2 text/long_text fields",
            len(text_fields) >= 2,
            hint=f"got {len(text_fields)}",
        )
        checks.check(
            ">=2 number fields",
            len(number_fields) >= 2,
            hint=f"got {len(number_fields)}",
        )
        checks.check(
            ">=1 boolean field",
            len(boolean_fields) >= 1,
            hint=f"got {len(boolean_fields)}",
        )
        checks.check(
            "Prep Time/Minutes field exists (number)",
            prep_number is not None,
            hint=f"number fields: {[f.name for f in number_fields]}",
        )
        checks.check(
            "Vegetarian field exists (boolean)",
            veg_bool is not None,
            hint=f"boolean fields: {[f.name for f in boolean_fields]}",
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
    err_count, err_hint = count_tool_errors(result)

    tables = Table.objects.filter(database=database)
    task_tables = [t for t in tables if "task" in t.name.lower()]
    table = task_tables[0] if task_tables else None
    fields = list(specific_iterator(table.field_set.all())) if table else []
    select_fields = [f for f in fields if isinstance(f, SingleSelectField)]
    status_field = next((f for f in select_fields if "status" in f.name.lower()), None)
    status_options = (
        list(status_field.select_options.values_list("value", flat=True))
        if status_field
        else []
    )
    date_fields = [f for f in fields if isinstance(f, DateField)]
    field_names_lower = {f.name.lower(): f for f in fields}
    priority_field = next(
        (f for f in select_fields if "priority" in f.name.lower()), None
    )
    priority_options = (
        list(priority_field.select_options.values_list("value", flat=True))
        if priority_field
        else []
    )
    status_option_values = {o.lower() for o in status_options}
    priority_option_values = {o.lower() for o in priority_options}

    with EvalChecklist("creates Tasks table with selects") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check(
            "Tasks table created",
            len(task_tables) == 1,
            hint=f"got {len(task_tables)}: {[t.name for t in tables]}",
        )
        checks.check(
            ">=2 single select fields (Status, Priority)",
            len(select_fields) >= 2,
            hint=f"got {len(select_fields)}: {[f.name for f in select_fields]}",
        )
        checks.check(
            "Status field exists",
            status_field is not None,
            hint=f"select fields: {[f.name for f in select_fields]}",
        )
        checks.check(
            "Status has >=3 options",
            len(status_options) >= 3,
            hint=f"got: {status_options}",
        )
        checks.check(
            ">=1 date field",
            len(date_fields) >= 1,
            hint=f"got {len(date_fields)}",
        )
        checks.check(
            "Title text field exists",
            any("title" in n for n in field_names_lower),
            hint=f"fields: {list(field_names_lower.keys())}",
        )
        checks.check(
            "Priority field exists",
            priority_field is not None,
            hint=f"select fields: {[f.name for f in select_fields]}",
        )
        checks.check(
            "Status has To Do / In Progress / Done",
            {"to do", "in progress", "done"} <= status_option_values,
            hint=f"got: {status_options}",
        )
        checks.check(
            "Priority has Low / Medium / High",
            {"low", "medium", "high"} <= priority_option_values,
            hint=f"got: {priority_options}",
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
    err_count, err_hint = count_tool_errors(result)

    tables = Table.objects.filter(database=database)
    table_names = {t.name.lower(): t for t in tables}
    project_tables = [name for name in table_names if "project" in name]
    task_tables = [name for name in table_names if "task" in name]

    task_table = table_names[task_tables[0]] if task_tables else None
    task_fields = (
        list(specific_iterator(task_table.field_set.all())) if task_table else []
    )
    link_fields = [f for f in task_fields if isinstance(f, LinkRowField)]

    project_table = table_names[project_tables[0]] if project_tables else None
    link_to_projects = (
        [f for f in link_fields if f.link_row_table_id == project_table.id]
        if project_table
        else []
    )
    project_fields = (
        list(specific_iterator(project_table.field_set.all())) if project_table else []
    )
    project_text_fields = [
        f for f in project_fields if isinstance(f, (TextField, LongTextField))
    ]
    task_select_fields = [f for f in task_fields if isinstance(f, SingleSelectField)]
    status_field_in_tasks = next(
        (f for f in task_select_fields if "status" in f.name.lower()), None
    )
    status_opts_in_tasks = (
        list(status_field_in_tasks.select_options.values_list("value", flat=True))
        if status_field_in_tasks
        else []
    )
    status_opt_values = {o.lower() for o in status_opts_in_tasks}

    with EvalChecklist("creates related tables") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check(
            "Projects table exists",
            len(project_tables) >= 1,
            hint=f"got tables: {list(table_names.keys())}",
        )
        checks.check(
            "Tasks table exists",
            len(task_tables) >= 1,
            hint=f"got tables: {list(table_names.keys())}",
        )
        checks.check(
            ">=1 link_row field in Tasks",
            len(link_fields) >= 1,
            hint=f"fields: {[(f.name, type(f).__name__) for f in task_fields]}",
        )
        checks.check(
            "link_row points to Projects table",
            len(link_to_projects) >= 1,
            hint=f"links to: {[(f.name, f.link_row_table_id) for f in link_fields]}",
        )
        checks.check(
            "Projects has >=2 text fields (Name, Description)",
            len(project_text_fields) >= 2,
            hint=f"project text fields: {[f.name for f in project_text_fields]}",
        )
        checks.check(
            "Tasks has Status single_select field",
            status_field_in_tasks is not None,
            hint=f"task select fields: {[f.name for f in task_select_fields]}",
        )
        checks.check(
            "Tasks Status has To Do / In Progress / Done",
            {"to do", "in progress", "done"} <= status_opt_values,
            hint=f"got: {status_opts_in_tasks}",
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
    err_count, err_hint = count_tool_errors(result)

    from baserow.contrib.database.models import Database

    databases = Database.objects.filter(workspace=workspace)
    tables = list(Table.objects.filter(database__in=databases))
    table_names_lower = [t.name.lower() for t in tables]

    books_table = next((t for t in tables if "book" in t.name.lower()), None)
    books_fields = (
        list(specific_iterator(books_table.field_set.all())) if books_table else []
    )
    books_field_types = {type(f) for f in books_fields}

    authors_table_obj = next((t for t in tables if "author" in t.name.lower()), None)
    authors_fields = (
        list(specific_iterator(authors_table_obj.field_set.all()))
        if authors_table_obj
        else []
    )
    authors_field_types = {type(f) for f in authors_fields}
    books_link_fields = [f for f in books_fields if isinstance(f, LinkRowField)]
    link_to_authors = (
        [f for f in books_link_fields if f.link_row_table_id == authors_table_obj.id]
        if authors_table_obj
        else []
    )

    with EvalChecklist("creates Bookstore database") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check(
            "database created",
            databases.exists(),
            hint="no database found in workspace",
        )
        checks.check(
            "Books table exists",
            any("book" in n for n in table_names_lower),
            hint=f"got: {[t.name for t in tables]}",
        )
        checks.check(
            "Authors table exists",
            any("author" in n for n in table_names_lower),
            hint=f"got: {[t.name for t in tables]}",
        )
        checks.check(
            "Books has text/long_text field",
            TextField in books_field_types or LongTextField in books_field_types,
            hint=f"field types: {[t.__name__ for t in books_field_types]}",
        )
        checks.check(
            "Books has number field (price)",
            NumberField in books_field_types,
            hint=f"field types: {[t.__name__ for t in books_field_types]}",
        )
        checks.check(
            "Books has date field",
            DateField in books_field_types,
            hint=f"field types: {[t.__name__ for t in books_field_types]}",
        )
        checks.check(
            "Books has link_row field to Authors",
            LinkRowField in books_field_types,
            hint=f"field types: {[t.__name__ for t in books_field_types]}",
        )
        checks.check(
            "Books link_row points to Authors table",
            len(link_to_authors) >= 1,
            hint=f"link targets: {[f.link_row_table_id for f in books_link_fields]}",
        )
        checks.check(
            "Authors has text field (name/bio)",
            TextField in authors_field_types or LongTextField in authors_field_types,
            hint=f"authors field types: {[t.__name__ for t in authors_field_types]}",
        )
        checks.check(
            "Books has >=2 text/long_text fields (title + description)",
            sum(1 for f in books_fields if isinstance(f, (TextField, LongTextField)))
            >= 2,
            hint=f"books text fields: {[f.name for f in books_fields if isinstance(f, (TextField, LongTextField))]}",
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
    pytest.param("grid", _setup_grid, PROMPT_CREATE_GRID_VIEW, id="grid"),
    pytest.param("kanban", _setup_kanban, PROMPT_CREATE_KANBAN_VIEW, id="kanban"),
    pytest.param(
        "calendar", _setup_calendar, PROMPT_CREATE_CALENDAR_VIEW, id="calendar"
    ),
    pytest.param("gallery", _setup_gallery, PROMPT_CREATE_GALLERY_VIEW, id="gallery"),
    pytest.param(
        "timeline", _setup_timeline, PROMPT_CREATE_TIMELINE_VIEW, id="timeline"
    ),
    pytest.param("form", _setup_form, PROMPT_CREATE_FORM_VIEW, id="form"),
]


_EXPECTED_VIEW_NAMES = {
    "grid": "all tasks",
    "kanban": "task board",
    "calendar": "schedule",
    "gallery": "image gallery",
    "timeline": "project timeline",
    "form": "submit task",
}


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
    err_count, err_hint = count_tool_errors(result)

    views = View.objects.filter(table=table)
    typed_views = [
        v for v in views if v.get_type().type == view_type and v.name != "Grid"
    ]

    view_name_ok = any(
        _EXPECTED_VIEW_NAMES[view_type] in v.name.lower() for v in typed_views
    )

    with EvalChecklist(f"creates {view_type} view") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check(
            f"{view_type} view created",
            len(typed_views) >= 1,
            hint=f"got views: {[(v.name, v.get_type().type) for v in views]}",
        )
        checks.check(
            "view name matches expected",
            view_name_ok,
            hint=f"expected '{_EXPECTED_VIEW_NAMES[view_type]}', got: {[v.name for v in typed_views]}",
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
        PROMPT_FILTER_TEXT_CONTAINS,
        "contains",
        "important",
        id="text_contains",
    ),
    pytest.param(
        "number",
        _setup_number_filter,
        PROMPT_FILTER_NUMBER_GREATER_THAN,
        "higher_than",
        "100",
        id="number_greater_than",
    ),
    pytest.param(
        "date",
        _setup_date_filter,
        PROMPT_FILTER_DATE_AFTER,
        "date_is_after",
        None,  # value contains UTC?date_mode format — fragile to check
        id="date_after",
    ),
    pytest.param(
        "single_select",
        _setup_single_select_filter,
        PROMPT_FILTER_SINGLE_SELECT_ANY_OF,
        "single_select_is_any_of",
        None,  # value is comma-separated option IDs — fragile to check
        id="single_select_is_any_of",
    ),
    pytest.param(
        "multiple_select",
        _setup_multiple_select_filter,
        PROMPT_FILTER_MULTIPLE_SELECT_HAS,
        "multiple_select_has",
        None,  # value is option ID — fragile to check
        id="multiple_select_has",
    ),
    pytest.param(
        "boolean",
        _setup_boolean_filter,
        PROMPT_FILTER_BOOLEAN_IS,
        "equal",
        "1",
        id="boolean_equal",
    ),
]


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "filter_type,setup_fn,prompt_template,expected_orm_type,expected_value_fragment",
    _FILTER_TEST_CASES,
)
def test_agent_creates_view_filter(
    data_fixture,
    eval_model,
    filter_type,
    setup_fn,
    prompt_template,
    expected_orm_type,
    expected_value_fragment,
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
    err_count, err_hint = count_tool_errors(result)

    filters = ViewFilter.objects.filter(view__table=table, type=expected_orm_type)
    all_filter_types = list(
        ViewFilter.objects.filter(view__table=table).values_list("type", flat=True)
    )
    filter_obj = filters.first()
    setup_field = list(extra.values())[0] if extra else None

    with EvalChecklist(f"creates {filter_type} view filter") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check(
            f"ViewFilter type='{expected_orm_type}' exists",
            filters.exists(),
            hint=f"got filter types: {all_filter_types}",
        )
        checks.check(
            "filter is on the correct field",
            filter_obj is not None
            and setup_field is not None
            and filter_obj.field_id == setup_field.id,
            hint=f"filter field_id={filter_obj.field_id if filter_obj else None}, expected={setup_field.id if setup_field else None}",
        )
        if expected_value_fragment is not None:
            checks.check(
                "filter value is correct",
                filter_obj is not None
                and expected_value_fragment in (filter_obj.value or ""),
                hint=f"filter value='{filter_obj.value if filter_obj else None}', expected fragment='{expected_value_fragment}'",
            )


# ---------------------------------------------------------------------------
# Field update/delete evals
# ---------------------------------------------------------------------------


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_renames_field(data_fixture, eval_model):
    """Agent should rename a field when asked."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Tasks")
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    data_fixture.create_long_text_field(table=table, name="Description")

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
        question=PROMPT_UPDATE_FIELD_RENAME.format(table_name=table.name),
        ui_context=ui_context,
    )

    print_message_history(result)
    err_count, err_hint = count_tool_errors(result)

    field_names = list(table.field_set.all().values_list("name", flat=True))

    with EvalChecklist("renames field") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check(
            "Summary field exists",
            any("summary" in n.lower() for n in field_names),
            hint=f"fields: {field_names}",
        )
        checks.check(
            "Description field gone",
            not any(n.lower() == "description" for n in field_names),
            hint=f"fields: {field_names}",
        )


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_updates_select_options(data_fixture, eval_model):
    """Agent should add a new option to a single_select field."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Tasks")
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    status_field = data_fixture.create_single_select_field(table=table, name="Status")
    data_fixture.create_select_option(field=status_field, value="To Do", order=1)
    data_fixture.create_select_option(field=status_field, value="Done", order=2)

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
        question=PROMPT_UPDATE_FIELD_SELECT_OPTIONS.format(table_name=table.name),
        ui_context=ui_context,
    )

    print_message_history(result)
    err_count, err_hint = count_tool_errors(result)

    status_field.refresh_from_db()
    options = list(status_field.select_options.values_list("value", flat=True))

    with EvalChecklist("updates select options") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check(
            "In Progress option added",
            any("in progress" in o.lower() for o in options),
            hint=f"options: {options}",
        )
        checks.check(
            "existing options preserved",
            {"to do", "done"} <= {o.lower() for o in options},
            hint=f"options: {options}",
        )


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_deletes_field(data_fixture, eval_model):
    """Agent should delete a field when asked."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Tasks")
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    data_fixture.create_long_text_field(table=table, name="Notes")
    data_fixture.create_text_field(table=table, name="Priority")

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
        question=PROMPT_DELETE_FIELD.format(table_name=table.name),
        ui_context=ui_context,
    )

    print_message_history(result)
    err_count, err_hint = count_tool_errors(result)

    field_names = list(table.field_set.all().values_list("name", flat=True))

    with EvalChecklist("deletes field") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check(
            "Notes field gone",
            not any(n.lower() == "notes" for n in field_names),
            hint=f"fields: {field_names}",
        )
        checks.check(
            "other fields preserved",
            any("name" in n.lower() for n in field_names)
            and any("priority" in n.lower() for n in field_names),
            hint=f"fields: {field_names}",
        )


# ---------------------------------------------------------------------------
# Sample rows eval
# ---------------------------------------------------------------------------


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_create_related_tables_with_sample_rows(data_fixture, eval_model):
    """
    Agent creates two related tables (Authors → Books) and sample rows
    are generated for both, including link_row references.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(
        workspace=workspace, name="Bookstore"
    )

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=25, model=eval_model
    )
    ui_context = build_database_ui_context(user, workspace, database)

    result = _run_agent(
        agent,
        deps,
        tracker,
        model,
        usage_limits,
        toolset,
        question=PROMPT_CREATE_RELATED_TABLES_WITH_SAMPLE_ROWS.format(
            database_name=database.name
        ),
        ui_context=ui_context,
    )

    print_message_history(result)
    err_count, err_hint = count_tool_errors(result)

    tables = Table.objects.filter(database=database)
    table_names = {t.name.lower(): t for t in tables}
    author_tables = [name for name in table_names if "author" in name]
    book_tables = [name for name in table_names if "book" in name]

    authors_count = (
        table_names[author_tables[0]].get_model().objects.count()
        if author_tables
        else 0
    )
    books_count = (
        table_names[book_tables[0]].get_model().objects.count() if book_tables else 0
    )
    books_table_obj = table_names[book_tables[0]] if book_tables else None
    books_fields_list = (
        list(specific_iterator(books_table_obj.field_set.all()))
        if books_table_obj
        else []
    )
    genre_field = next(
        (
            f
            for f in books_fields_list
            if isinstance(f, SingleSelectField) and "genre" in f.name.lower()
        ),
        None,
    )
    genre_options = (
        list(genre_field.select_options.values_list("value", flat=True))
        if genre_field
        else []
    )
    genre_option_values = {o.lower() for o in genre_options}
    price_field = next(
        (
            f
            for f in books_fields_list
            if isinstance(f, NumberField) and "price" in f.name.lower()
        ),
        None,
    )
    books_link_fields_list = [
        f for f in books_fields_list if isinstance(f, LinkRowField)
    ]

    with EvalChecklist("creates Bookstore with sample rows") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check(
            "Authors table exists",
            len(author_tables) >= 1,
            hint=f"got: {list(table_names.keys())}",
        )
        checks.check(
            "Books table exists",
            len(book_tables) >= 1,
            hint=f"got: {list(table_names.keys())}",
        )
        checks.check(
            "Authors has >=1 sample row",
            authors_count >= 1,
            hint=f"got {authors_count}",
        )
        checks.check(
            "Books has >=2 sample rows",
            books_count >= 2,
            hint=f"got {books_count}",
        )
        checks.check(
            "Books has Genre single_select field",
            genre_field is not None,
            hint=f"books select fields: {[f.name for f in books_fields_list if isinstance(f, SingleSelectField)]}",
        )
        checks.check(
            "Genre has Fiction / Non-Fiction / Science / History options",
            {"fiction", "non-fiction", "science", "history"} <= genre_option_values,
            hint=f"got: {genre_options}",
        )
        checks.check(
            "Books has Price (number) field",
            price_field is not None,
            hint=f"books number fields: {[f.name for f in books_fields_list if isinstance(f, NumberField)]}",
        )
        checks.check(
            "Books has link_row to Authors",
            len(books_link_fields_list) >= 1,
            hint=f"books fields: {[f.name for f in books_fields_list]}",
        )
