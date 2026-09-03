"""Kuma-database eval dataset: table/view/filter/field/row actions."""

from __future__ import annotations

from django.contrib.auth.models import AbstractUser

from baserow.contrib.database.fields.models import (
    BooleanField,
    DateField,
    LinkRowField,
    LongTextField,
    NumberField,
    SingleSelectField,
    TextField,
)
from baserow.contrib.database.models import Database, Table
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.views.models import View, ViewFilter
from baserow.core.db import specific_iterator
from baserow.core.models import Workspace
from baserow.test_utils.fixtures import Fixtures
from baserow_enterprise.assistant.evals.registry import (
    register_case,
    register_scenario,
)
from baserow_enterprise.assistant.evals.scenarios import build_database_ui_context
from baserow_enterprise.assistant.evals.types import (
    CheckResult,
    CheckSuite,
    EvalCase,
    EvalRunOutput,
    EvalScenario,
)

# ---------------------------------------------------------------------------
# Table creation
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


@register_scenario("database-creates-simple-table")
def _creates_simple_table_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(
        workspace=workspace, name="Recipe Database"
    )
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database),
        refs={"database": database},
    )


def _check_creates_simple_table(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    database = scenario.refs["database"]
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

    return [
        CheckResult(
            "Recipes table created",
            len(recipe_tables) == 1,
            hint=f"got {len(recipe_tables)}: {[t.name for t in tables]}",
        ),
        CheckResult(
            "Name field exists",
            any("name" in n for n in field_names),
            hint=f"fields: {list(field_names.keys())}",
        ),
        CheckResult(
            "Description field exists",
            any("description" in n for n in field_names),
            hint=f"fields: {list(field_names.keys())}",
        ),
        CheckResult(
            ">=2 text/long_text fields",
            len(text_fields) >= 2,
            hint=f"got {len(text_fields)}",
        ),
        CheckResult(
            ">=2 number fields",
            len(number_fields) >= 2,
            hint=f"got {len(number_fields)}",
        ),
        CheckResult(
            ">=1 boolean field",
            len(boolean_fields) >= 1,
            hint=f"got {len(boolean_fields)}",
        ),
        CheckResult(
            "Prep Time/Minutes field exists (number)",
            prep_number is not None,
            hint=f"number fields: {[f.name for f in number_fields]}",
        ),
        CheckResult(
            "Vegetarian field exists (boolean)",
            veg_bool is not None,
            hint=f"boolean fields: {[f.name for f in boolean_fields]}",
        ),
    ]


register_case(
    EvalCase(
        id="database/creates-simple-table",
        dataset="kuma-database",
        prompt=PROMPT_CREATES_SIMPLE_TABLE.format(database_name="Recipe Database"),
        scenario="database-creates-simple-table",
        checks=_check_creates_simple_table,
        max_iters=15,
    )
)


@register_scenario("database-creates-table-with-select-fields")
def _creates_table_with_select_fields_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(
        workspace=workspace, name="Task Management"
    )
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database),
        refs={"database": database},
    )


def _check_creates_table_with_select_fields(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    database = scenario.refs["database"]
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

    return [
        CheckResult(
            "Tasks table created",
            len(task_tables) == 1,
            hint=f"got {len(task_tables)}: {[t.name for t in tables]}",
        ),
        CheckResult(
            ">=2 single select fields (Status, Priority)",
            len(select_fields) >= 2,
            hint=f"got {len(select_fields)}: {[f.name for f in select_fields]}",
        ),
        CheckResult(
            "Status field exists",
            status_field is not None,
            hint=f"select fields: {[f.name for f in select_fields]}",
        ),
        CheckResult(
            "Status has >=3 options",
            len(status_options) >= 3,
            hint=f"got: {status_options}",
        ),
        CheckResult(
            ">=1 date field", len(date_fields) >= 1, hint=f"got {len(date_fields)}"
        ),
        CheckResult(
            "Title text field exists",
            any("title" in n for n in field_names_lower),
            hint=f"fields: {list(field_names_lower.keys())}",
        ),
        CheckResult(
            "Priority field exists",
            priority_field is not None,
            hint=f"select fields: {[f.name for f in select_fields]}",
        ),
        CheckResult(
            "Status has To Do / In Progress / Done",
            {"to do", "in progress", "done"} <= status_option_values,
            hint=f"got: {status_options}",
        ),
        CheckResult(
            "Priority has Low / Medium / High",
            {"low", "medium", "high"} <= priority_option_values,
            hint=f"got: {priority_options}",
        ),
    ]


register_case(
    EvalCase(
        id="database/creates-table-with-select-fields",
        dataset="kuma-database",
        prompt=PROMPT_CREATES_TABLE_WITH_SELECT_FIELDS.format(
            database_name="Task Management"
        ),
        scenario="database-creates-table-with-select-fields",
        checks=_check_creates_table_with_select_fields,
        max_iters=15,
    )
)


@register_scenario("database-creates-related-tables")
def _creates_related_tables_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(
        workspace=workspace, name="Project Management"
    )
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database),
        refs={"database": database},
    )


def _check_creates_related_tables(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    database = scenario.refs["database"]
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

    return [
        CheckResult(
            "Projects table exists",
            len(project_tables) >= 1,
            hint=f"got tables: {list(table_names.keys())}",
        ),
        CheckResult(
            "Tasks table exists",
            len(task_tables) >= 1,
            hint=f"got tables: {list(table_names.keys())}",
        ),
        CheckResult(
            ">=1 link_row field in Tasks",
            len(link_fields) >= 1,
            hint=f"fields: {[(f.name, type(f).__name__) for f in task_fields]}",
        ),
        CheckResult(
            "link_row points to Projects table",
            len(link_to_projects) >= 1,
            hint=f"links to: {[(f.name, f.link_row_table_id) for f in link_fields]}",
        ),
        CheckResult(
            "Projects has >=2 text fields (Name, Description)",
            len(project_text_fields) >= 2,
            hint=f"project text fields: {[f.name for f in project_text_fields]}",
        ),
        CheckResult(
            "Tasks has Status single_select field",
            status_field_in_tasks is not None,
            hint=f"task select fields: {[f.name for f in task_select_fields]}",
        ),
        CheckResult(
            "Tasks Status has To Do / In Progress / Done",
            {"to do", "in progress", "done"} <= status_opt_values,
            hint=f"got: {status_opts_in_tasks}",
        ),
    ]


register_case(
    EvalCase(
        id="database/creates-related-tables",
        dataset="kuma-database",
        prompt=PROMPT_CREATES_RELATED_TABLES.format(database_name="Project Management"),
        scenario="database-creates-related-tables",
        checks=_check_creates_related_tables,
        max_iters=20,
    )
)


@register_scenario("database-creates-database-from-description")
def _creates_database_from_description_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace),
    )


def _check_creates_database_from_description(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    databases = Database.objects.filter(workspace=scenario.workspace)
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

    return [
        CheckResult(
            "database created",
            databases.exists(),
            hint="no database found in workspace",
        ),
        CheckResult(
            "Books table exists",
            any("book" in n for n in table_names_lower),
            hint=f"got: {[t.name for t in tables]}",
        ),
        CheckResult(
            "Authors table exists",
            any("author" in n for n in table_names_lower),
            hint=f"got: {[t.name for t in tables]}",
        ),
        CheckResult(
            "Books has text/long_text field",
            TextField in books_field_types or LongTextField in books_field_types,
            hint=f"field types: {[t.__name__ for t in books_field_types]}",
        ),
        CheckResult(
            "Books has number field (price)",
            NumberField in books_field_types,
            hint=f"field types: {[t.__name__ for t in books_field_types]}",
        ),
        CheckResult(
            "Books has date field",
            DateField in books_field_types,
            hint=f"field types: {[t.__name__ for t in books_field_types]}",
        ),
        CheckResult(
            "Books has link_row field to Authors",
            LinkRowField in books_field_types,
            hint=f"field types: {[t.__name__ for t in books_field_types]}",
        ),
        CheckResult(
            "Books link_row points to Authors table",
            len(link_to_authors) >= 1,
            hint=f"link targets: {[f.link_row_table_id for f in books_link_fields]}",
        ),
        CheckResult(
            "Authors has text field (name/bio)",
            TextField in authors_field_types or LongTextField in authors_field_types,
            hint=f"authors field types: {[t.__name__ for t in authors_field_types]}",
        ),
        CheckResult(
            "Books has >=2 text/long_text fields (title + description)",
            sum(1 for f in books_fields if isinstance(f, (TextField, LongTextField)))
            >= 2,
            hint=(
                "books text fields: "
                f"{[f.name for f in books_fields if isinstance(f, (TextField, LongTextField))]}"
            ),
        ),
    ]


register_case(
    EvalCase(
        id="database/creates-database-from-description",
        dataset="kuma-database",
        prompt=PROMPT_CREATES_DATABASE_FROM_DESCRIPTION,
        scenario="database-creates-database-from-description",
        checks=_check_creates_database_from_description,
        max_iters=25,
    )
)


@register_scenario("database-creates-related-tables-with-sample-rows")
def _creates_related_tables_with_sample_rows_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(workspace=workspace, name="Bookstore")
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database),
        refs={"database": database},
    )


def _check_creates_related_tables_with_sample_rows(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    database = scenario.refs["database"]
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

    return [
        CheckResult(
            "Authors table exists",
            len(author_tables) >= 1,
            hint=f"got: {list(table_names.keys())}",
        ),
        CheckResult(
            "Books table exists",
            len(book_tables) >= 1,
            hint=f"got: {list(table_names.keys())}",
        ),
        CheckResult(
            "Authors has >=1 sample row",
            authors_count >= 1,
            hint=f"got {authors_count}",
        ),
        CheckResult(
            "Books has >=2 sample rows", books_count >= 2, hint=f"got {books_count}"
        ),
        CheckResult(
            "Books has Genre single_select field",
            genre_field is not None,
            hint=(
                "books select fields: "
                f"{[f.name for f in books_fields_list if isinstance(f, SingleSelectField)]}"
            ),
        ),
        CheckResult(
            "Genre has Fiction / Non-Fiction / Science / History options",
            {"fiction", "non-fiction", "science", "history"} <= genre_option_values,
            hint=f"got: {genre_options}",
        ),
        CheckResult(
            "Books has Price (number) field",
            price_field is not None,
            hint=(
                "books number fields: "
                f"{[f.name for f in books_fields_list if isinstance(f, NumberField)]}"
            ),
        ),
        CheckResult(
            "Books has link_row to Authors",
            len(books_link_fields_list) >= 1,
            hint=f"books fields: {[f.name for f in books_fields_list]}",
        ),
    ]


register_case(
    EvalCase(
        id="database/creates-related-tables-with-sample-rows",
        dataset="kuma-database",
        prompt=PROMPT_CREATE_RELATED_TABLES_WITH_SAMPLE_ROWS.format(
            database_name="Bookstore"
        ),
        scenario="database-creates-related-tables-with-sample-rows",
        checks=_check_creates_related_tables_with_sample_rows,
        max_iters=25,
    )
)


# ---------------------------------------------------------------------------
# View creation matrix (6 scenarios, one per view type)
# ---------------------------------------------------------------------------

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

_EXPECTED_VIEW_NAMES = {
    "grid": "all tasks",
    "kanban": "task board",
    "calendar": "schedule",
    "gallery": "image gallery",
    "timeline": "project timeline",
    "form": "submit task",
}

_TasksTable = tuple[AbstractUser, Workspace, Database, Table]


def _make_tasks_table(fx: Fixtures) -> _TasksTable:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(workspace=workspace)
    table = fx.create_database_table(database=database, name="Tasks")
    fx.create_text_field(table=table, name="Name", primary=True)
    return user, workspace, database, table


def _check_creates_view(view_type: str) -> CheckSuite:
    def _checks(
        case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
    ) -> list[CheckResult]:
        table = scenario.refs["table"]
        views = View.objects.filter(table=table)
        typed_views = [
            v for v in views if v.get_type().type == view_type and v.name != "Grid"
        ]
        view_name_ok = any(
            _EXPECTED_VIEW_NAMES[view_type] in v.name.lower() for v in typed_views
        )
        return [
            CheckResult(
                f"{view_type} view created",
                len(typed_views) >= 1,
                hint=f"got views: {[(v.name, v.get_type().type) for v in views]}",
            ),
            CheckResult(
                "view name matches expected",
                view_name_ok,
                hint=(
                    f"expected '{_EXPECTED_VIEW_NAMES[view_type]}', "
                    f"got: {[v.name for v in typed_views]}"
                ),
            ),
        ]

    return _checks


@register_scenario("database-view-grid")
def _view_grid_scenario(fx: Fixtures) -> EvalScenario:
    user, workspace, database, table = _make_tasks_table(fx)
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database, table),
        refs={"table": table},
    )


register_case(
    EvalCase(
        id="database/creates-view-grid",
        dataset="kuma-database",
        prompt=PROMPT_CREATE_GRID_VIEW.format(table_name="Tasks"),
        scenario="database-view-grid",
        checks=_check_creates_view("grid"),
        max_iters=15,
    )
)


@register_scenario("database-view-kanban")
def _view_kanban_scenario(fx: Fixtures) -> EvalScenario:
    user, workspace, database, table = _make_tasks_table(fx)
    status_field = fx.create_single_select_field(table=table, name="Status")
    fx.create_select_option(field=status_field, value="To Do", order=1)
    fx.create_select_option(field=status_field, value="In Progress", order=2)
    fx.create_select_option(field=status_field, value="Done", order=3)
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database, table),
        refs={"table": table, "status_field": status_field},
    )


register_case(
    EvalCase(
        id="database/creates-view-kanban",
        dataset="kuma-database",
        prompt=PROMPT_CREATE_KANBAN_VIEW.format(
            table_name="Tasks", status_field_name="Status"
        ),
        scenario="database-view-kanban",
        checks=_check_creates_view("kanban"),
        max_iters=15,
    )
)


@register_scenario("database-view-calendar")
def _view_calendar_scenario(fx: Fixtures) -> EvalScenario:
    user, workspace, database, table = _make_tasks_table(fx)
    date_field = fx.create_date_field(table=table, name="Due Date")
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database, table),
        refs={"table": table, "date_field": date_field},
    )


register_case(
    EvalCase(
        id="database/creates-view-calendar",
        dataset="kuma-database",
        prompt=PROMPT_CREATE_CALENDAR_VIEW.format(
            table_name="Tasks", date_field_name="Due Date"
        ),
        scenario="database-view-calendar",
        checks=_check_creates_view("calendar"),
        max_iters=15,
    )
)


@register_scenario("database-view-gallery")
def _view_gallery_scenario(fx: Fixtures) -> EvalScenario:
    user, workspace, database, table = _make_tasks_table(fx)
    file_field = fx.create_file_field(table=table, name="Cover Image")
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database, table),
        refs={"table": table, "file_field": file_field},
    )


register_case(
    EvalCase(
        id="database/creates-view-gallery",
        dataset="kuma-database",
        prompt=PROMPT_CREATE_GALLERY_VIEW.format(
            table_name="Tasks", file_field_name="Cover Image"
        ),
        scenario="database-view-gallery",
        checks=_check_creates_view("gallery"),
        max_iters=15,
    )
)


@register_scenario("database-view-timeline")
def _view_timeline_scenario(fx: Fixtures) -> EvalScenario:
    user, workspace, database, table = _make_tasks_table(fx)
    start_field = fx.create_date_field(
        table=table, name="Start Date", date_include_time=False
    )
    end_field = fx.create_date_field(
        table=table, name="End Date", date_include_time=False
    )
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database, table),
        refs={"table": table, "start_field": start_field, "end_field": end_field},
    )


register_case(
    EvalCase(
        id="database/creates-view-timeline",
        dataset="kuma-database",
        prompt=PROMPT_CREATE_TIMELINE_VIEW.format(
            table_name="Tasks",
            start_field_name="Start Date",
            end_field_name="End Date",
        ),
        scenario="database-view-timeline",
        checks=_check_creates_view("timeline"),
        max_iters=15,
    )
)


@register_scenario("database-view-form")
def _view_form_scenario(fx: Fixtures) -> EvalScenario:
    user, workspace, database, table = _make_tasks_table(fx)
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database, table),
        refs={"table": table},
    )


register_case(
    EvalCase(
        id="database/creates-view-form",
        dataset="kuma-database",
        prompt=PROMPT_CREATE_FORM_VIEW.format(table_name="Tasks"),
        scenario="database-view-form",
        checks=_check_creates_view("form"),
        max_iters=15,
    )
)


# ---------------------------------------------------------------------------
# View filter creation matrix (6 scenarios, one per filter type)
# ---------------------------------------------------------------------------

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


def _check_creates_filter(
    expected_orm_type: str, expected_value_fragment: str | None
) -> CheckSuite:
    def _checks(
        case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
    ) -> list[CheckResult]:
        table = scenario.refs["table"]
        setup_field = scenario.refs["filter_field"]
        filters = ViewFilter.objects.filter(view__table=table, type=expected_orm_type)
        all_filter_types = list(
            ViewFilter.objects.filter(view__table=table).values_list("type", flat=True)
        )
        filter_obj = filters.first()

        checks = [
            CheckResult(
                f"ViewFilter type='{expected_orm_type}' exists",
                filters.exists(),
                hint=f"got filter types: {all_filter_types}",
            ),
            CheckResult(
                "filter is on the correct field",
                filter_obj is not None and filter_obj.field_id == setup_field.id,
                hint=(
                    f"filter field_id={filter_obj.field_id if filter_obj else None}, "
                    f"expected={setup_field.id}"
                ),
            ),
        ]
        # date/single_select/multiple_select values are timezone/option-id
        # encoded and too fragile to check verbatim.
        if expected_value_fragment is not None:
            checks.append(
                CheckResult(
                    "filter value is correct",
                    filter_obj is not None
                    and expected_value_fragment in (filter_obj.value or ""),
                    hint=(
                        f"filter value='{filter_obj.value if filter_obj else None}', "
                        f"expected fragment='{expected_value_fragment}'"
                    ),
                )
            )
        return checks

    return _checks


@register_scenario("database-filter-text-contains")
def _filter_text_contains_scenario(fx: Fixtures) -> EvalScenario:
    user, workspace, database, table = _make_tasks_table(fx)
    field = fx.create_text_field(table=table, name="Description")
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database, table),
        refs={"table": table, "filter_field": field},
    )


register_case(
    EvalCase(
        id="database/creates-view-filter-text-contains",
        dataset="kuma-database",
        prompt=PROMPT_FILTER_TEXT_CONTAINS.format(
            table_name="Tasks", text_field_name="Description"
        ),
        scenario="database-filter-text-contains",
        checks=_check_creates_filter("contains", "important"),
        max_iters=15,
    )
)


@register_scenario("database-filter-number-greater-than")
def _filter_number_greater_than_scenario(fx: Fixtures) -> EvalScenario:
    user, workspace, database, table = _make_tasks_table(fx)
    field = fx.create_number_field(table=table, name="Amount")
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database, table),
        refs={"table": table, "filter_field": field},
    )


register_case(
    EvalCase(
        id="database/creates-view-filter-number-greater-than",
        dataset="kuma-database",
        prompt=PROMPT_FILTER_NUMBER_GREATER_THAN.format(
            table_name="Tasks", number_field_name="Amount"
        ),
        scenario="database-filter-number-greater-than",
        checks=_check_creates_filter("higher_than", "100"),
        max_iters=15,
    )
)


@register_scenario("database-filter-date-after")
def _filter_date_after_scenario(fx: Fixtures) -> EvalScenario:
    user, workspace, database, table = _make_tasks_table(fx)
    field = fx.create_date_field(table=table, name="Due Date")
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database, table),
        refs={"table": table, "filter_field": field},
    )


register_case(
    EvalCase(
        id="database/creates-view-filter-date-after",
        dataset="kuma-database",
        prompt=PROMPT_FILTER_DATE_AFTER.format(
            table_name="Tasks", date_field_name="Due Date"
        ),
        scenario="database-filter-date-after",
        checks=_check_creates_filter("date_is_after", None),
        max_iters=15,
    )
)


@register_scenario("database-filter-single-select-is-any-of")
def _filter_single_select_is_any_of_scenario(fx: Fixtures) -> EvalScenario:
    user, workspace, database, table = _make_tasks_table(fx)
    field = fx.create_single_select_field(table=table, name="Status")
    fx.create_select_option(field=field, value="Active", order=1)
    fx.create_select_option(field=field, value="Pending", order=2)
    fx.create_select_option(field=field, value="Closed", order=3)
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database, table),
        refs={"table": table, "filter_field": field},
    )


register_case(
    EvalCase(
        id="database/creates-view-filter-single-select-is-any-of",
        dataset="kuma-database",
        prompt=PROMPT_FILTER_SINGLE_SELECT_ANY_OF.format(
            table_name="Tasks", select_field_name="Status"
        ),
        scenario="database-filter-single-select-is-any-of",
        checks=_check_creates_filter("single_select_is_any_of", None),
        max_iters=15,
    )
)


@register_scenario("database-filter-multiple-select-has")
def _filter_multiple_select_has_scenario(fx: Fixtures) -> EvalScenario:
    user, workspace, database, table = _make_tasks_table(fx)
    field = fx.create_multiple_select_field(table=table, name="Tags")
    fx.create_select_option(field=field, value="Important", order=1)
    fx.create_select_option(field=field, value="Urgent", order=2)
    fx.create_select_option(field=field, value="Low", order=3)
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database, table),
        refs={"table": table, "filter_field": field},
    )


register_case(
    EvalCase(
        id="database/creates-view-filter-multiple-select-has",
        dataset="kuma-database",
        prompt=PROMPT_FILTER_MULTIPLE_SELECT_HAS.format(
            table_name="Tasks", multi_field_name="Tags"
        ),
        scenario="database-filter-multiple-select-has",
        checks=_check_creates_filter("multiple_select_has", None),
        max_iters=15,
    )
)


@register_scenario("database-filter-boolean-equal")
def _filter_boolean_equal_scenario(fx: Fixtures) -> EvalScenario:
    user, workspace, database, table = _make_tasks_table(fx)
    field = fx.create_boolean_field(table=table, name="Active")
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database, table),
        refs={"table": table, "filter_field": field},
    )


register_case(
    EvalCase(
        id="database/creates-view-filter-boolean-equal",
        dataset="kuma-database",
        prompt=PROMPT_FILTER_BOOLEAN_IS.format(
            table_name="Tasks", bool_field_name="Active"
        ),
        scenario="database-filter-boolean-equal",
        checks=_check_creates_filter("equal", "1"),
        max_iters=15,
    )
)


# ---------------------------------------------------------------------------
# Field update/delete
# ---------------------------------------------------------------------------

PROMPT_UPDATE_FIELD_RENAME = (
    "Rename the Description field to Summary in the {table_name} table."
)

PROMPT_UPDATE_FIELD_SELECT_OPTIONS = (
    "Add an 'In Progress' option to the Status field in the {table_name} table."
)

PROMPT_DELETE_FIELD = "Delete the Notes field from the {table_name} table."


@register_scenario("database-renames-field")
def _renames_field_scenario(fx: Fixtures) -> EvalScenario:
    user, workspace, database, table = _make_tasks_table(fx)
    fx.create_long_text_field(table=table, name="Description")
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database, table),
        refs={"table": table},
    )


def _check_renames_field(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    table = scenario.refs["table"]
    field_names = list(table.field_set.all().values_list("name", flat=True))
    return [
        CheckResult(
            "Summary field exists",
            any("summary" in n.lower() for n in field_names),
            hint=f"fields: {field_names}",
        ),
        CheckResult(
            "Description field gone",
            not any(n.lower() == "description" for n in field_names),
            hint=f"fields: {field_names}",
        ),
    ]


register_case(
    EvalCase(
        id="database/renames-field",
        dataset="kuma-database",
        prompt=PROMPT_UPDATE_FIELD_RENAME.format(table_name="Tasks"),
        scenario="database-renames-field",
        checks=_check_renames_field,
        max_iters=15,
    )
)


@register_scenario("database-updates-select-options")
def _updates_select_options_scenario(fx: Fixtures) -> EvalScenario:
    user, workspace, database, table = _make_tasks_table(fx)
    status_field = fx.create_single_select_field(table=table, name="Status")
    fx.create_select_option(field=status_field, value="To Do", order=1)
    fx.create_select_option(field=status_field, value="Done", order=2)
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database, table),
        refs={"status_field": status_field},
    )


def _check_updates_select_options(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    status_field = scenario.refs["status_field"]
    status_field.refresh_from_db()
    options = list(status_field.select_options.values_list("value", flat=True))
    return [
        CheckResult(
            "In Progress option added",
            any("in progress" in o.lower() for o in options),
            hint=f"options: {options}",
        ),
        CheckResult(
            "existing options preserved",
            {"to do", "done"} <= {o.lower() for o in options},
            hint=f"options: {options}",
        ),
    ]


register_case(
    EvalCase(
        id="database/updates-select-options",
        dataset="kuma-database",
        prompt=PROMPT_UPDATE_FIELD_SELECT_OPTIONS.format(table_name="Tasks"),
        scenario="database-updates-select-options",
        checks=_check_updates_select_options,
        max_iters=15,
    )
)


@register_scenario("database-deletes-field")
def _deletes_field_scenario(fx: Fixtures) -> EvalScenario:
    user, workspace, database, table = _make_tasks_table(fx)
    fx.create_long_text_field(table=table, name="Notes")
    fx.create_text_field(table=table, name="Priority")
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database, table),
        refs={"table": table},
    )


def _check_deletes_field(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    table = scenario.refs["table"]
    field_names = list(table.field_set.all().values_list("name", flat=True))
    return [
        CheckResult(
            "Notes field gone",
            not any(n.lower() == "notes" for n in field_names),
            hint=f"fields: {field_names}",
        ),
        CheckResult(
            "other fields preserved",
            any("name" in n.lower() for n in field_names)
            and any("priority" in n.lower() for n in field_names),
            hint=f"fields: {field_names}",
        ),
    ]


register_case(
    EvalCase(
        id="database/deletes-field",
        dataset="kuma-database",
        prompt=PROMPT_DELETE_FIELD.format(table_name="Tasks"),
        scenario="database-deletes-field",
        checks=_check_deletes_field,
        max_iters=15,
    )
)


# ---------------------------------------------------------------------------
# Rows: create rows across every managed field type
# ---------------------------------------------------------------------------

PROMPT_CREATES_ROWS_WITH_ALL_FIELD_TYPES = (
    "Create 5 rows with diverse sample data in table {table_name}. "
    "Fill in ALL fields with realistic values."
)


@register_scenario("database-creates-rows-with-all-field-types")
def _creates_rows_with_all_field_types_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(workspace=workspace)

    linked_table = fx.create_database_table(database=database, name="Categories")
    linked_primary = fx.create_text_field(table=linked_table, name="Name", primary=True)
    RowHandler().force_create_rows(
        user,
        linked_table,
        [
            {linked_primary.db_column: "Work"},
            {linked_primary.db_column: "Personal"},
            {linked_primary.db_column: "Urgent"},
        ],
    )

    table = fx.create_database_table(database=database, name="Tasks")
    title = fx.create_text_field(table=table, name="Title", primary=True)
    description = fx.create_long_text_field(table=table, name="Description")
    estimated_hours = fx.create_number_field(
        table=table, name="Estimated Hours", number_decimal_places=1
    )
    completed = fx.create_boolean_field(table=table, name="Completed")
    due_date = fx.create_date_field(table=table, name="Due Date")
    created_at = fx.create_date_field(
        table=table, name="Created At", date_include_time=True
    )

    status_field = fx.create_single_select_field(table=table, name="Status")
    fx.create_select_option(field=status_field, value="To Do", order=0)
    fx.create_select_option(field=status_field, value="In Progress", order=1)
    fx.create_select_option(field=status_field, value="Done", order=2)

    tags_field = fx.create_multiple_select_field(table=table, name="Tags")
    fx.create_select_option(field=tags_field, value="Bug", order=0)
    fx.create_select_option(field=tags_field, value="Feature", order=1)
    fx.create_select_option(field=tags_field, value="Docs", order=2)

    category_field = fx.create_link_row_field(
        table=table,
        link_row_table=linked_table,
        name="Category",
        link_row_multiple_relationships=False,
    )
    related_categories_field = fx.create_link_row_field(
        table=table,
        link_row_table=linked_table,
        name="Related Categories",
        link_row_multiple_relationships=True,
    )

    fields = {
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
    }

    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database, table=table),
        refs={"table": table, "fields": fields},
    )


def _check_creates_rows_with_all_field_types(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    table = scenario.refs["table"]
    fields = scenario.refs["fields"]
    table_model = table.get_model()
    row_count = table_model.objects.count()
    sample_rows = list(table_model.objects.all())

    def _get_field_value(row, field_name):
        return getattr(row, fields[field_name].db_column, None)

    def _any_row(check_fn):
        return any(check_fn(r) for r in sample_rows)

    return [
        CheckResult("5 rows created", row_count == 5, hint=f"got {row_count}"),
        CheckResult(
            "title populated", _any_row(lambda r: bool(_get_field_value(r, "title")))
        ),
        CheckResult(
            "description populated",
            _any_row(lambda r: bool(_get_field_value(r, "description"))),
        ),
        CheckResult(
            "estimated_hours populated",
            _any_row(lambda r: _get_field_value(r, "estimated_hours") is not None),
        ),
        CheckResult(
            "estimated_hours > 0 in at least one row",
            _any_row(lambda r: (_get_field_value(r, "estimated_hours") or 0) > 0),
        ),
        CheckResult(
            "completed has at least one True",
            _any_row(lambda r: _get_field_value(r, "completed") is True),
        ),
        CheckResult(
            "due_date populated",
            _any_row(lambda r: _get_field_value(r, "due_date") is not None),
        ),
        CheckResult(
            "created_at populated",
            _any_row(lambda r: _get_field_value(r, "created_at") is not None),
        ),
        CheckResult(
            "status is a known option",
            _any_row(
                lambda r: bool(_get_field_value(r, "status"))
                and _get_field_value(r, "status").value
                in ["To Do", "In Progress", "Done"]
            ),
        ),
        CheckResult(
            "tags has at least one known option",
            _any_row(
                lambda r: bool(
                    set(_get_field_value(r, "tags").values_list("value", flat=True))
                    & {"Bug", "Feature", "Docs"}
                )
            ),
        ),
        CheckResult(
            "category linked",
            _any_row(lambda r: len(_get_field_value(r, "category").all()) > 0),
        ),
        CheckResult(
            "related_categories linked",
            _any_row(
                lambda r: len(_get_field_value(r, "related_categories").all()) > 0
            ),
        ),
    ]


register_case(
    EvalCase(
        id="database/creates-rows-with-all-field-types",
        dataset="kuma-database",
        prompt=PROMPT_CREATES_ROWS_WITH_ALL_FIELD_TYPES.format(table_name="Tasks"),
        scenario="database-creates-rows-with-all-field-types",
        checks=_check_creates_rows_with_all_field_types,
        max_iters=20,
    )
)
