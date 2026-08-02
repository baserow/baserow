from django.apps import apps
from django.db import connection

import pytest

from baserow.contrib.database.migrations.helpers.migrate_button_url_formula_to_open_url_action import (  # noqa: E501
    migrate_button_url_formulas_to_open_url_actions,
)
from baserow.contrib.database.workflow_actions.models import OpenUrlWorkflowAction


def set_raw_url_formula(button_field, raw_value):
    """
    Writes straight past the field's serialisation, so the column can hold a
    shape the ORM would never write itself.
    """

    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE database_buttonfield SET url_formula = %s WHERE field_ptr_id = %s",
            [raw_value, button_field.id],
        )


@pytest.mark.django_db
def test_url_formula_becomes_an_open_url_action(data_fixture):
    table = data_fixture.create_database_table()
    button_field = data_fixture.create_button_field(
        table=table,
        name="btn",
        url_formula={"formula": "'https://example.com'", "mode": "advanced"},
    )

    migrate_button_url_formulas_to_open_url_actions(apps, None)

    action = OpenUrlWorkflowAction.objects.get(field_id=button_field.id)
    assert action.order == 1
    # The retired attribute always opened a new tab, so the action it becomes
    # keeps doing that rather than taking the new "self" default.
    assert action.target == "blank"
    assert action.url["formula"] == "'https://example.com'"
    # The mode has to survive too: a raw formula downgraded to simple stops
    # resolving entirely.
    assert action.url["mode"] == "advanced"
    assert action.content_type.model == "openurlworkflowaction"


@pytest.mark.django_db
def test_a_legacy_bare_string_url_formula_becomes_an_open_url_action(data_fixture):
    table = data_fixture.create_database_table()
    button_field = data_fixture.create_button_field(table=table, name="btn")
    # Rows written before the formula column held JSON keep a bare string.
    set_raw_url_formula(button_field, "'https://example.com'")

    migrate_button_url_formulas_to_open_url_actions(apps, None)

    action = OpenUrlWorkflowAction.objects.get(field_id=button_field.id)
    assert action.url["formula"] == "'https://example.com'"
    assert action.target == "blank"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "raw_value",
    [
        # A NULL column, which `exclude(url_formula="")` would have kept rather
        # than skipped, and both serialisations of an empty formula: the key
        # order differs depending on whether the value was stored from a string
        # or from a dict, so no single text comparison matches them all.
        None,
        "",
        '{"f": "", "m": "simple", "v": "0.1"}',
        '{"m": "simple", "v": "0.1", "f": ""}',
    ],
)
def test_button_without_a_url_formula_gets_no_action(data_fixture, raw_value):
    table = data_fixture.create_database_table()
    button_field = data_fixture.create_button_field(table=table, name="btn")
    set_raw_url_formula(button_field, raw_value)

    migrate_button_url_formulas_to_open_url_actions(apps, None)

    assert not OpenUrlWorkflowAction.objects.filter(field_id=button_field.id).exists()


@pytest.mark.django_db
def test_running_twice_does_not_stack_a_second_action(data_fixture):
    table = data_fixture.create_database_table()
    button_field = data_fixture.create_button_field(
        table=table,
        name="btn",
        url_formula={"formula": "'https://example.com'", "mode": "simple"},
    )

    migrate_button_url_formulas_to_open_url_actions(apps, None)
    migrate_button_url_formulas_to_open_url_actions(apps, None)

    assert OpenUrlWorkflowAction.objects.filter(field_id=button_field.id).count() == 1
