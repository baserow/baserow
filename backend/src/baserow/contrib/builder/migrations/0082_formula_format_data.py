import json

from django.db import migrations

# The stored shape of a formula object, see `baserow.core.formula.field`. The
# application code is deliberately not imported: this migration must keep
# working whatever the code looks like later.
FORMULA_VERSION = "0.1"
BATCH_SIZE = 1000


def load_formula_object(value):
    """
    Returns the stored formula object of a `FormulaField` value, or `None` when
    the value is a legacy plain string (or empty) rather than a serialized
    object.
    """

    if not value or not value.startswith("{"):
        return None
    try:
        formula_object = json.loads(value)
    except (TypeError, ValueError):
        return None
    if not isinstance(formula_object, dict) or "f" not in formula_object:
        return None
    return formula_object


def raw_formula(text):
    """
    The stored form of a raw-mode formula holding the given text, written the
    way `FormulaField.get_prep_value` writes it. An empty name stays an empty
    formula, so "no name" keeps meaning "no name".
    """

    return json.dumps({"m": "raw", "v": FORMULA_VERSION, "f": text or ""})


def iter_batches(cursor, table, id_column, columns, where=None):
    """
    Yields the rows of `table` in id-ordered batches, so that a large table
    is never loaded into memory at once. Each row is `(id, *columns)`.
    """

    select = ", ".join([id_column, *columns])
    condition = f"AND {where}" if where else ""
    last_id = 0
    while True:
        cursor.execute(
            f"SELECT {select} FROM {table} "  # noqa: S608
            f"WHERE {id_column} > %s {condition} "
            f"ORDER BY {id_column} LIMIT %s",
            [last_id, BATCH_SIZE],
        )
        rows = cursor.fetchall()
        if not rows:
            return
        yield rows
        last_id = rows[-1][0]


def wrap_collection_field_names(apps, schema_editor):
    """
    Wraps the plain-string names of collection fields (the table headers) into
    raw-mode formula objects, the shape the column's `FormulaField` now writes.

    The field reads a plain string as a raw-mode formula
    anyway, this only gives every row the same shape. Idempotent: a value that
    already is a formula object is left alone.
    """

    with schema_editor.connection.cursor() as cursor:
        for rows in iter_batches(cursor, "builder_collectionfield", "id", ["name"]):
            updates = [
                (raw_formula(name), row_id)
                for row_id, name in rows
                if load_formula_object(name) is None
            ]
            if updates:
                cursor.executemany(
                    "UPDATE builder_collectionfield SET name = %s WHERE id = %s",
                    updates,
                )


def wrap_choice_option_names(apps, schema_editor):
    """
    Same as `wrap_collection_field_names`, for the names of the manual options
    of the Choice elements.
    """

    with schema_editor.connection.cursor() as cursor:
        for rows in iter_batches(
            cursor, "builder_choiceelementoption", "id", ["name"]
        ):
            updates = [
                (raw_formula(name), row_id)
                for row_id, name in rows
                if load_formula_object(name) is None
            ]
            if updates:
                cursor.executemany(
                    "UPDATE builder_choiceelementoption SET name = %s WHERE id = %s",
                    updates,
                )


def copy_text_element_format(apps, schema_editor):
    """
    Copies the deprecated `format` column of the Text elements into the `fmt`
    key of their `value`, where the format now lives. Only markdown rows need
    it: a value without `fmt` is plain. Idempotent: a value that already has a
    `fmt` is left alone.
    """

    with schema_editor.connection.cursor() as cursor:
        for rows in iter_batches(
            cursor,
            "builder_textelement",
            "element_ptr_id",
            ["value"],
            where="format = 'markdown'",
        ):
            updates = []
            for row_id, value in rows:
                formula_object = load_formula_object(value)
                if formula_object is None:
                    # A legacy value: the bare formula string, in simple mode.
                    formula_object = {
                        "m": "simple",
                        "v": FORMULA_VERSION,
                        "f": value or "",
                    }
                elif "fmt" in formula_object:
                    continue
                formula_object["fmt"] = "markdown"
                updates.append((json.dumps(formula_object), row_id))
            if updates:
                cursor.executemany(
                    "UPDATE builder_textelement SET value = %s "
                    "WHERE element_ptr_id = %s",
                    updates,
                )


class Migration(migrations.Migration):
    dependencies = [
        ("builder", "0081_alter_collectionfield_name_alter_textelement_format"),
    ]

    operations = [
        migrations.RunPython(wrap_collection_field_names, migrations.RunPython.noop),
        migrations.RunPython(wrap_choice_option_names, migrations.RunPython.noop),
        migrations.RunPython(copy_text_element_format, migrations.RunPython.noop),
    ]
