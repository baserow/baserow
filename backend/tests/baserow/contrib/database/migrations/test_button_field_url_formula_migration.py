# noinspection PyPep8Naming
from django.db import connection

import pytest

# The shape the formula column stores: the formula, its mode, and the version.
ADVANCED = '{"f": "\'https://advanced.test\'", "m": "advanced", "v": "0.1"}'
SIMPLE = '{"f": "\'https://simple.test\'", "m": "simple", "v": "0.1"}'
# Rows written before the column held JSON keep a bare string.
BARE = "'https://bare.test'"
EMPTY = '{"f": "", "m": "simple", "v": "0.1"}'


def set_raw_url_formula(field_id, raw_value):
    """
    Writes straight past the field's serialisation, so the column can hold a
    shape the ORM would never write itself.
    """

    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE database_buttonfield SET url_formula = %s WHERE field_ptr_id = %s",
            [raw_value, field_id],
        )


def url_formula_column_exists():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'database_buttonfield' "
            "AND column_name = 'url_formula'"
        )
        return cursor.fetchone() is not None


@pytest.mark.once_per_day_in_ci
def test_url_formulas_become_open_url_actions(migrator, teardown_table_metadata):
    """
    The upgrade path a button field takes: 0216 moves every `url_formula` into
    an `open_url` action, and only then does 0217 drop the column.
    """

    migrate_from = [
        ("database", "0215_view_public_id_index"),
        ("core", "0115_ai_provider"),
    ]
    migrate_to = [("database", "0217_remove_buttonfield_url_formula")]

    old_state = migrator.migrate(migrate_from)

    ContentType = old_state.apps.get_model("contenttypes", "ContentType")
    Workspace = old_state.apps.get_model("core", "Workspace")
    Database = old_state.apps.get_model("database", "Database")
    Table = old_state.apps.get_model("database", "Table")
    ButtonField = old_state.apps.get_model("database", "ButtonField")

    assert url_formula_column_exists()

    workspace = Workspace.objects.create(name="workspace")
    database = Database.objects.create(
        content_type=ContentType.objects.get_for_model(Database),
        order=1,
        name="database",
        workspace_id=workspace.id,
        trashed=False,
    )
    table = Table.objects.create(
        database_id=database.id, name="table", order=1, trashed=False
    )
    button_content_type_id = ContentType.objects.get_for_model(ButtonField).id

    def button(name, raw_value):
        field = ButtonField.objects.create(
            table_id=table.id,
            name=name,
            order=1,
            content_type_id=button_content_type_id,
            label="Go",
        )
        set_raw_url_formula(field.field_ptr_id, raw_value)
        return field.field_ptr_id

    advanced = button("advanced", ADVANCED)
    simple = button("simple", SIMPLE)
    bare = button("bare", BARE)
    empty = button("empty", EMPTY)
    blank = button("blank", "")
    null = button("null", None)

    new_state = migrator.migrate(migrate_to)

    OpenUrlWorkflowAction = new_state.apps.get_model(
        "database", "OpenUrlWorkflowAction"
    )

    action = OpenUrlWorkflowAction.objects.get(field_id=advanced)
    assert action.url["formula"] == "'https://advanced.test'"
    # A raw formula downgraded to simple stops resolving entirely.
    assert action.url["mode"] == "advanced"
    # `url_formula` always opened a new tab, so the action keeps doing that
    # rather than taking the "self" default.
    assert action.target == "blank"
    assert action.order == 1

    kept = OpenUrlWorkflowAction.objects.get(field_id=simple)
    assert kept.url["formula"] == "'https://simple.test'"
    assert kept.url["mode"] == "simple"
    assert (
        OpenUrlWorkflowAction.objects.get(field_id=bare).url["formula"]
        == "'https://bare.test'"
    )

    # A button that opened nothing has nothing to run.
    assert not OpenUrlWorkflowAction.objects.filter(
        field_id__in=[empty, blank, null]
    ).exists()

    # Only once every formula has been moved is the column dropped.
    assert not url_formula_column_exists()
