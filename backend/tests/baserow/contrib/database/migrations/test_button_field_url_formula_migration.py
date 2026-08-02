from django.apps import apps

import pytest

from baserow.contrib.database.migrations.helpers.migrate_button_url_formula_to_open_url_action import (  # noqa: E501
    migrate_button_url_formulas_to_open_url_actions,
)
from baserow.contrib.database.workflow_actions.models import OpenUrlWorkflowAction


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
def test_button_without_a_url_formula_gets_no_action(data_fixture):
    table = data_fixture.create_database_table()
    button_field = data_fixture.create_button_field(table=table, name="btn")

    migrate_button_url_formulas_to_open_url_actions(apps, None)

    assert not OpenUrlWorkflowAction.objects.filter(field_id=button_field.id).exists()
