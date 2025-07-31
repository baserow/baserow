from datetime import timedelta
from decimal import Decimal
from typing import cast

from django.db import connection, transaction
from django.urls import reverse

import pytest
from pytest_unordered import unordered
from rest_framework.status import HTTP_200_OK

from baserow.contrib.database.fields.actions import (
    ChangePrimaryFieldActionType,
    DuplicateFieldActionType,
    UpdateFieldActionType,
)
from baserow.contrib.database.fields.exceptions import FieldDoesNotExist
from baserow.contrib.database.fields.field_types import TextFieldType
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import (
    LinkRowField,
    MultipleSelectField,
    NumberField,
    RatingField,
    SpecificFieldForUpdate,
    TextField,
)
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.action.handler import ActionHandler
from baserow.core.action.models import Action
from baserow.core.action.registries import action_type_registry
from baserow.core.models import WORKSPACE_USER_PERMISSION_ADMIN
from baserow.core.trash.handler import TrashHandler
from baserow.test_utils.helpers import (
    assert_serialized_field_values_are_the_same,
    assert_undo_redo_actions_are_valid,
    extract_serialized_field_value,
    setup_interesting_test_table,
)


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_updating_field_name_only_doesnt_create_backup(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    field = data_fixture.create_boolean_field(user=user, name="field")

    action_type_registry.get_by_type(UpdateFieldActionType).do(user, field, name="test")
    field.refresh_from_db()
    assert field.name == "test"

    actions = ActionHandler.undo(
        user, [UpdateFieldActionType.scope(field.table_id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])

    assert actions[0].params["backup_data"] is None
    field.refresh_from_db()
    assert field.name == "field"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_updating_formula_fields_formula_doesnt_make_backup(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(user=user)
    formula_field = FieldHandler().create_field(
        user, table, "formula", formula="1+1", name="test"
    )

    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user, cast(SpecificFieldForUpdate, formula_field), formula="1+2"
    )
    created_action = Action.objects.first()
    assert created_action.params["backup_data"] is None


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_updating_formula_field_to_other_type_doesnt_make_backup(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(user=user)
    formula_field = FieldHandler().create_field(
        user, table, "formula", formula="1+1", name="test"
    )

    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user, cast(SpecificFieldForUpdate, formula_field), new_type_name="text"
    )
    created_action = Action.objects.first()
    assert created_action.params["backup_data"] is None


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_updating_field_name_only_and_undoing_after_naming_collisions_works(
    data_fixture,
):
    session_id = "session-id"
    starting_field_name = "field"
    user = data_fixture.create_user(session_id=session_id)
    field = data_fixture.create_boolean_field(user=user, name=starting_field_name)
    user2 = data_fixture.create_user()
    data_fixture.create_user_workspace(
        user=user2,
        workspace=field.table.database.workspace,
        permissions=WORKSPACE_USER_PERMISSION_ADMIN,
    )

    action_type_registry.get_by_type(UpdateFieldActionType).do(user, field, name="test")
    field.refresh_from_db()
    assert field.name == "test"

    # Create a new field which clashes with the undo
    FieldHandler().create_field(
        user2, field.table, TextFieldType.type, name=starting_field_name
    )

    actions = ActionHandler.undo(
        user, [UpdateFieldActionType.scope(field.table_id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])
    field.refresh_from_db()
    assert field.name == starting_field_name + " (From undo)"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_updating_field_name_only_and_redoing_after_naming_collisions_works(
    data_fixture,
):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    user2 = data_fixture.create_user()
    starting_field_name = "field"
    field = data_fixture.create_boolean_field(user=user, name=starting_field_name)
    data_fixture.create_user_workspace(
        user=user2,
        workspace=field.table.database.workspace,
        permissions=WORKSPACE_USER_PERMISSION_ADMIN,
    )

    new_field_name = "test"
    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user, field, name=new_field_name
    )

    actions = ActionHandler.undo(
        user, [UpdateFieldActionType.scope(field.table_id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])

    # Create a new field which clashes with the redo
    FieldHandler().create_field(
        user2, field.table, TextFieldType.type, name=new_field_name
    )

    actions = ActionHandler.redo(
        user, [UpdateFieldActionType.scope(field.table_id)], session_id
    )

    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])
    field.refresh_from_db()
    assert field.name == new_field_name + " (From redo)"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_updating_field(data_fixture, django_assert_num_queries):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    original_text_default = "text_default"
    field = data_fixture.create_text_field(
        user=user, name="field", text_default=original_text_default
    )
    model = field.table.get_model(attribute_names=True)
    model.objects.bulk_create(
        [
            model(field="A"),
            model(field="B"),
            model(field="C"),
            model(field="1"),
            model(field="2"),
            model(field="3"),
        ]
    )

    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user, field, new_type_name="number"
    )
    model = field.table.get_model(attribute_names=True)

    assert list(model.objects.values_list("field", flat=True)) == [
        None,
        None,
        None,
        Decimal("1"),
        Decimal("2"),
        Decimal("3"),
    ]

    actions = ActionHandler.undo(
        user, [UpdateFieldActionType.scope(field.table_id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])

    undone_field = FieldHandler().get_field(field.id, TextField)
    assert undone_field.text_default == original_text_default

    model = field.table.get_model(attribute_names=True)
    assert list(model.objects.values_list("field", flat=True)) == [
        "A",
        "B",
        "C",
        "1",
        "2",
        "3",
    ]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_and_redo_converting_link_row_to_other_type_related(
    data_fixture, api_client, django_assert_num_queries
):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)
    token = data_fixture.generate_token(user=user)
    grid_view_a = data_fixture.create_grid_view(user=user, table=table_a)
    grid_view_b = data_fixture.create_grid_view(user=user, table=table_b)

    model_a = table_a.get_model()
    row_a_1 = model_a.objects.create()
    row_a_2 = model_a.objects.create()

    model_b = table_b.get_model()
    row_b_1 = model_b.objects.create()
    row_b_2 = model_b.objects.create()

    getattr(row_a_1, f"field_{link_field.id}").set([row_b_1.id, row_b_2.id])
    getattr(row_a_2, f"field_{link_field.id}").set([row_b_2.id])

    row_a_1.save()
    row_a_2.save()

    related_field = link_field.link_row_related_field
    related_field_id = related_field.id
    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user, related_field, new_type_name="text"
    )

    # Make sure that the link field was removed from the other table
    assert not table_a.field_set.filter(id=link_field.id).exists()
    assert LinkRowField.objects.filter(table=table_a).count() == 0
    assert LinkRowField.objects.filter(table=table_b).count() == 0

    # Make sure that the content of the previously linked row field is now deleted
    model_b = table_b.get_model()
    assert list(model_b.objects.values_list(related_field.db_column, flat=True)) == [
        None,
        None,
    ]

    actions = ActionHandler.undo(
        user, [UpdateFieldActionType.scope(related_field.table_id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])

    related_field = LinkRowField.objects.get(id=related_field_id)
    link_field = related_field.link_row_related_field
    # Make sure that the link field was restored to the other table
    assert table_a.field_set.filter(id=related_field.link_row_related_field.id).exists()
    assert table_b.field_set.filter(id=related_field.id).exists()

    assert LinkRowField.objects.filter(table=table_a).count() == 1
    assert LinkRowField.objects.filter(table=table_b).count() == 1
    link_row_in_first_table = LinkRowField.objects.get(table=table_a)
    link_row_in_second_table = LinkRowField.objects.get(table=table_b)
    assert link_row_in_first_table.link_row_related_field == link_row_in_second_table
    assert link_row_in_second_table.link_row_related_field == link_row_in_first_table

    # Make sure that the content of the previously linked row field is now restored
    model_a = table_a.get_model()
    model_b = table_b.get_model()
    row_a_1 = model_a.objects.get(id=row_a_1.id)
    row_a_2 = model_a.objects.get(id=row_a_2.id)
    row_b_1 = model_b.objects.get(id=row_b_1.id)
    row_b_2 = model_b.objects.get(id=row_b_2.id)

    assert list(
        getattr(row_a_1, f"field_{link_field.id}").values_list("id", flat=True)
    ) == [row_b_1.id, row_b_2.id]
    assert list(
        getattr(row_a_2, f"field_{link_field.id}").values_list("id", flat=True)
    ) == [row_b_2.id]
    assert list(
        getattr(row_b_1, f"field_{link_field.link_row_related_field.id}").values_list(
            "id", flat=True
        )
    ) == [row_a_1.id]
    assert list(
        getattr(row_b_2, f"field_{link_field.link_row_related_field.id}").values_list(
            "id", flat=True
        )
    ) == [row_a_1.id, row_a_2.id]

    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view_a.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    assert response.status_code == HTTP_200_OK
    url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view_b.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
@pytest.mark.undo_redo(transaction=True)
def test_undoing_link_row_type_change_can_still_insert_new_relations_after(
    data_fixture,
):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)

    model = table_a.get_model()
    row_a_1 = model.objects.create()
    row_a_2 = model.objects.create()

    model_b = table_b.get_model()
    row_b_1 = model_b.objects.create()
    row_b_2 = model_b.objects.create()

    getattr(row_a_1, f"field_{link_field.id}").set([row_b_1.id, row_b_2.id])
    getattr(row_a_2, f"field_{link_field.id}").set([row_b_2.id])

    row_a_1.save()
    row_a_2.save()

    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user, link_field, new_type_name="text"
    )
    with transaction.atomic():
        actions = ActionHandler.undo(
            user, [UpdateFieldActionType.scope(link_field.table_id)], session_id
        )
        assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])

    with transaction.atomic():
        RowHandler().update_row(
            user, table_a, row_a_2, {f"field_{link_field.id}": [row_b_1.id, row_b_2.id]}
        )

    row_a_2.refresh_from_db()
    assert list(
        getattr(row_a_2, f"field_{link_field.id}").values_list("id", flat=True)
    ) == [row_b_1.id, row_b_2.id]


@pytest.mark.django_db
@pytest.mark.undo_redo
@pytest.mark.field_link_row
def test_can_undo_and_redo_linkrow_deleting_one_side_relationships(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)

    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user, link_field, name="A->B", has_related_field=False
    )

    link_field.refresh_from_db()
    assert link_field.link_row_related_field_id is None
    assert table_a.linkrowfield_set.count() == 0

    actions = ActionHandler.undo(
        user, [UpdateFieldActionType.scope(link_field.table_id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])
    # Make sure that the link field was restored to the other table
    link_field.refresh_from_db()
    assert link_field.link_row_related_field_id is not None
    assert table_a.linkrowfield_set.count() == 1

    actions = ActionHandler.redo(
        user, [UpdateFieldActionType.scope(link_field.table_id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])
    # Make sure that the link field was deleted again in the other table
    link_field.refresh_from_db()
    assert link_field.link_row_related_field_id is None
    assert table_a.linkrowfield_set.count() == 0


@pytest.mark.django_db
@pytest.mark.undo_redo
@pytest.mark.field_link_row
def test_can_undo_and_redo_converting_link_row_to_other_type(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)
    link_row_related_field_id = link_field.link_row_related_field_id

    model = table_a.get_model()
    row_a_1 = model.objects.create()
    row_a_2 = model.objects.create()

    model_b = table_b.get_model()
    row_b_1 = model_b.objects.create()
    row_b_2 = model_b.objects.create()

    getattr(row_a_1, f"field_{link_field.id}").set([row_b_1.id, row_b_2.id])
    getattr(row_a_2, f"field_{link_field.id}").set([row_b_2.id])

    row_a_1.save()
    row_a_2.save()

    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user, link_field, new_type_name="text"
    )

    # Make sure that the link field was removed from the other table
    assert not table_b.field_set.filter(id=link_row_related_field_id).exists()

    # Make sure that the content of the previously linked row field is now deleted
    model = table_a.get_model()
    assert list(model.objects.values_list(link_field.db_column, flat=True)) == [
        None,
        None,
    ]

    actions = ActionHandler.undo(
        user, [UpdateFieldActionType.scope(link_field.table_id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])
    link_field = LinkRowField.objects.get(id=link_field.id)
    # Make sure that the link field was restored to the other table
    assert table_b.field_set.filter(id=link_field.link_row_related_field.id).exists()

    # Make sure that the content of the previously linked row field is now restored
    row_a_1.refresh_from_db()
    row_a_2.refresh_from_db()

    assert list(
        getattr(row_a_1, f"field_{link_field.id}").values_list("id", flat=True)
    ) == [row_b_1.id, row_b_2.id]
    assert list(
        getattr(row_a_2, f"field_{link_field.id}").values_list("id", flat=True)
    ) == [row_b_2.id]

    actions = ActionHandler.redo(
        user, [UpdateFieldActionType.scope(link_field.table_id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])

    # Make sure that the link field was removed from the other table
    assert not table_b.field_set.filter(id=link_row_related_field_id).exists()

    # Make sure that the content of the previously linked row field is now deleted
    model = table_a.get_model()
    assert list(model.objects.values_list(link_field.db_column, flat=True)) == [
        None,
        None,
    ]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_and_redo_converting_multi_select_to_other_type(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(user=user)
    multi_select_field = data_fixture.create_multiple_select_field(
        user=user, table=table
    )

    option_a = data_fixture.create_select_option(
        field=multi_select_field, value="x", color="blue"
    )
    option_b = data_fixture.create_select_option(
        field=multi_select_field, value="y", color="red"
    )

    model = table.get_model()
    row_a = model.objects.create()
    row_b = model.objects.create()
    row_c = model.objects.create()

    getattr(row_a, f"field_{multi_select_field.id}").set([option_a.id, option_b.id])
    getattr(row_b, f"field_{multi_select_field.id}").set([option_a.id])
    getattr(row_c, f"field_{multi_select_field.id}").set([])

    row_a.save()
    row_b.save()
    row_c.save()

    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user, multi_select_field, new_type_name="file"
    )

    assert not multi_select_field.select_options.exists()

    model = table.get_model()
    assert list(model.objects.values_list(multi_select_field.db_column, flat=True)) == [
        [],
        [],
        [],
    ]

    actions = ActionHandler.undo(
        user, [UpdateFieldActionType.scope(multi_select_field.table_id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])
    multi_select_field = MultipleSelectField.objects.get(id=multi_select_field.id)

    assert multi_select_field.select_options.count() == 2

    row_a.refresh_from_db()
    row_b.refresh_from_db()
    row_c.refresh_from_db()

    assert list(
        getattr(row_a, f"field_{multi_select_field.id}").values_list("id", flat=True)
    ) == unordered([option_a.id, option_b.id])
    assert list(
        getattr(row_b, f"field_{multi_select_field.id}").values_list("id", flat=True)
    ) == [option_a.id]
    assert (
        list(
            getattr(row_c, f"field_{multi_select_field.id}").values_list(
                "id", flat=True
            )
        )
        == []
    )

    actions = ActionHandler.redo(
        user, [UpdateFieldActionType.scope(multi_select_field.table_id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])

    assert not multi_select_field.select_options.exists()

    model = table.get_model()
    assert list(model.objects.values_list(multi_select_field.db_column, flat=True)) == [
        [],
        [],
        [],
    ]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_and_redo_removing_multi_select_option(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(user=user)
    multi_select_field = data_fixture.create_multiple_select_field(
        user=user, table=table
    )

    option_a = data_fixture.create_select_option(
        field=multi_select_field, value="x", color="blue"
    )
    option_b = data_fixture.create_select_option(
        field=multi_select_field, value="y", color="red"
    )

    model = table.get_model()
    row_a = model.objects.create()
    row_b = model.objects.create()
    row_c = model.objects.create()

    getattr(row_a, f"field_{multi_select_field.id}").set([option_a.id, option_b.id])
    getattr(row_b, f"field_{multi_select_field.id}").set([option_a.id])
    getattr(row_c, f"field_{multi_select_field.id}").set([])

    row_a.save()
    row_b.save()
    row_c.save()

    # Remove option b
    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user,
        multi_select_field,
        select_options=[
            {
                "id": option_a.id,
                "value": "x",
                "color": "red",
            }
        ],
    )

    assert multi_select_field.select_options.count() == 1

    row_a.refresh_from_db()
    row_b.refresh_from_db()
    row_c.refresh_from_db()

    assert list(
        getattr(row_a, f"field_{multi_select_field.id}").values_list("id", flat=True)
    ) == [option_a.id]
    assert list(
        getattr(row_b, f"field_{multi_select_field.id}").values_list("id", flat=True)
    ) == [option_a.id]
    assert (
        list(
            getattr(row_c, f"field_{multi_select_field.id}").values_list(
                "id", flat=True
            )
        )
        == []
    )

    actions = ActionHandler.undo(
        user, [UpdateFieldActionType.scope(multi_select_field.table_id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])
    multi_select_field = MultipleSelectField.objects.get(id=multi_select_field.id)

    assert multi_select_field.select_options.count() == 2

    row_a.refresh_from_db()
    row_b.refresh_from_db()
    row_c.refresh_from_db()

    assert list(
        getattr(row_a, f"field_{multi_select_field.id}").values_list("id", flat=True)
    ) == unordered([option_a.id, option_b.id])
    assert list(
        getattr(row_b, f"field_{multi_select_field.id}").values_list("id", flat=True)
    ) == [option_a.id]
    assert (
        list(
            getattr(row_c, f"field_{multi_select_field.id}").values_list(
                "id", flat=True
            )
        )
        == []
    )

    actions = ActionHandler.redo(
        user, [UpdateFieldActionType.scope(multi_select_field.table_id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])

    assert multi_select_field.select_options.count() == 1

    row_a.refresh_from_db()
    row_b.refresh_from_db()
    row_c.refresh_from_db()

    assert list(
        getattr(row_a, f"field_{multi_select_field.id}").values_list("id", flat=True)
    ) == [option_a.id]
    assert list(
        getattr(row_b, f"field_{multi_select_field.id}").values_list("id", flat=True)
    ) == [option_a.id]
    assert (
        list(
            getattr(row_c, f"field_{multi_select_field.id}").values_list(
                "id", flat=True
            )
        )
        == []
    )


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_cleaning_up_undo_link_row_action_deletes_m2m_table(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)
    m2m_link_row_table_name = link_field.through_table_name

    model = table_a.get_model()
    row_a_1 = model.objects.create()
    row_a_2 = model.objects.create()

    model_b = table_b.get_model()
    row_b_1 = model_b.objects.create()
    row_b_2 = model_b.objects.create()

    getattr(row_a_1, f"field_{link_field.id}").set([row_b_1.id, row_b_2.id])
    getattr(row_a_2, f"field_{link_field.id}").set([row_b_2.id])

    row_a_1.save()
    row_a_2.save()

    update_field_action_type = action_type_registry.get_by_type(UpdateFieldActionType)
    update_field_action_type.do(user, link_field, new_type_name="text")

    assert m2m_link_row_table_name not in connection.introspection.table_names()

    action = Action.objects.first()
    backup_table_name = dict(action.params)["backup_data"]["backed_up_m2m_table_name"]
    assert backup_table_name in connection.introspection.table_names()

    update_field_action_type.clean_up_any_extra_action_data(action)

    assert backup_table_name not in connection.introspection.table_names()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_still_cleanup_m2m_backup_after_field_perm_deleted(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)
    m2m_link_row_table_name = link_field.through_table_name

    model = table_a.get_model()
    row_a_1 = model.objects.create()
    row_a_2 = model.objects.create()

    model_b = table_b.get_model()
    row_b_1 = model_b.objects.create()
    row_b_2 = model_b.objects.create()

    getattr(row_a_1, f"field_{link_field.id}").set([row_b_1.id, row_b_2.id])
    getattr(row_a_2, f"field_{link_field.id}").set([row_b_2.id])

    row_a_1.save()
    row_a_2.save()

    update_field_action_type = action_type_registry.get_by_type(UpdateFieldActionType)
    update_field_action_type.do(user, link_field, new_type_name="text")

    assert m2m_link_row_table_name not in connection.introspection.table_names()

    action = Action.objects.first()
    backup_table_name = dict(action.params)["backup_data"]["backed_up_m2m_table_name"]

    TrashHandler().permanently_delete(link_field)
    assert backup_table_name in connection.introspection.table_names()

    update_field_action_type.clean_up_any_extra_action_data(action)

    assert backup_table_name not in connection.introspection.table_names()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_cleaning_up_undo_single_column_field_action_deletes_column(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    text_field = data_fixture.create_text_field(user=user)

    update_field_action_type = action_type_registry.get_by_type(UpdateFieldActionType)
    update_field_action_type.do(user, text_field, new_type_name="number")

    action = Action.objects.first()
    backup_column_name = dict(action.params)["backup_data"]["backed_up_column_name"]
    assert backup_column_name in get_table_column_names(text_field)

    update_field_action_type.clean_up_any_extra_action_data(action)

    assert backup_column_name not in get_table_column_names(text_field)


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_cleaning_up_undo_single_column_perm_deleted_field_action_deletes_column(
    data_fixture,
):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    text_field = data_fixture.create_text_field(user=user)

    update_field_action_type = action_type_registry.get_by_type(UpdateFieldActionType)
    update_field_action_type.do(user, text_field, new_type_name="number")

    action = Action.objects.first()
    backup_column_name = dict(action.params)["backup_data"]["backed_up_column_name"]
    assert backup_column_name in get_table_column_names(text_field)

    TrashHandler().permanently_delete(NumberField.objects.get(id=text_field.id))

    update_field_action_type.clean_up_any_extra_action_data(action)

    assert backup_column_name not in get_table_column_names(text_field)


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_cleaning_up_undo_single_column_perm_deleted_table_doesnt_crash(
    data_fixture,
):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    text_field = data_fixture.create_text_field(user=user)
    table = text_field.table

    update_field_action_type = action_type_registry.get_by_type(UpdateFieldActionType)
    update_field_action_type.do(user, text_field, new_type_name="number")

    action = Action.objects.first()

    TrashHandler().permanently_delete(table)

    # The cleanup shouldn't crash if the table (and backup column) has already been
    # deleted.
    update_field_action_type.clean_up_any_extra_action_data(action)


def get_table_column_names(field):
    with connection.cursor() as cursor:
        cursor.execute(f"Select * FROM {field.table.get_database_table_name()} LIMIT 0")
        return [desc[0] for desc in cursor.description]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_insert_row_when_backup_fields_exist(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    option_field = data_fixture.create_single_select_field(
        user=user, name="singleselect"
    )
    option_a = data_fixture.create_select_option(
        field=option_field, value="x", color="blue"
    )
    option_b = data_fixture.create_select_option(
        field=option_field, value="y", color="red"
    )

    model = option_field.table.get_model(attribute_names=True)
    model.objects.bulk_create(
        [
            model(singleselect=option_a),
            model(singleselect=option_b),
            model(singleselect=None),
        ]
    )

    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user, option_field, new_type_name="file"
    )
    actions = ActionHandler.undo(
        user, [UpdateFieldActionType.scope(option_field.table_id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])
    assert actions[0].params["backup_data"] is not None

    row = RowHandler().create_row(user, option_field.table, {})
    assert row.id is not None


@pytest.mark.django_db
@pytest.mark.undo_redo
@pytest.mark.field_single_select
def test_can_undo_redo_converting_away_from_single_select(
    data_fixture, django_assert_num_queries
):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    option_field = data_fixture.create_single_select_field(
        user=user, name="singleselect"
    )
    option_a = data_fixture.create_select_option(
        field=option_field, value="x", color="blue"
    )
    option_b = data_fixture.create_select_option(
        field=option_field, value="y", color="red"
    )

    model = option_field.table.get_model(attribute_names=True)
    model.objects.bulk_create(
        [
            model(singleselect=option_a),
            model(singleselect=option_b),
            model(singleselect=None),
        ]
    )

    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user, option_field, new_type_name="file"
    )
    model = option_field.table.get_model(attribute_names=True)

    assert list(model.objects.values_list("singleselect", flat=True)) == [
        [],
        [],
        [],
    ]

    actions = ActionHandler.undo(
        user, [UpdateFieldActionType.scope(option_field.table_id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])

    model = option_field.table.get_model(attribute_names=True)
    assert list(model.objects.values_list("singleselect", flat=True)) == [
        option_a.id,
        option_b.id,
        None,
    ]
    assert option_field.select_options.count() == 2

    actions = ActionHandler.redo(
        user, [UpdateFieldActionType.scope(option_field.table_id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])

    model = option_field.table.get_model(attribute_names=True)
    assert list(model.objects.values_list("singleselect", flat=True)) == [[], [], []]
    assert option_field.select_options.count() == 0


@pytest.mark.django_db
@pytest.mark.undo_redo
@pytest.mark.field_single_select
def test_can_undo_redo_adding_select_option(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    user2 = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_user_workspace(
        user=user2, workspace=table.database.workspace, permissions="ADMIN"
    )

    option_field = data_fixture.create_single_select_field(
        user=user, table=table, name="singleselect"
    )
    option_a = data_fixture.create_select_option(
        field=option_field, value="x", color="blue"
    )
    option_b = data_fixture.create_select_option(
        field=option_field, value="y", color="red"
    )

    model = table.get_model(attribute_names=True)
    model.objects.bulk_create(
        [
            model(singleselect=option_a),
            model(singleselect=option_b),
            model(singleselect=None),
        ]
    )

    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user,
        option_field,
        select_options=[
            {"id": option_a.id, "value": "x", "color": "blue"},
            {"id": option_b.id, "value": "y", "color": "red"},
            {"value": "z", "color": "yellow"},
        ],
    )

    assert option_field.select_options.count() == 3
    new_option = option_field.select_options.filter(value="z").get()

    row_with_new_option = model.objects.create(singleselect=new_option)

    assert list(model.objects.values_list("singleselect__value", flat=True)) == [
        "x",
        "y",
        None,
        "z",
    ]

    # The second user then makes their own select option.
    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user2,
        option_field,
        select_options=[
            {"id": option_a.id, "value": "x", "color": "blue"},
            {"id": option_b.id, "value": "y", "color": "red"},
            {"id": new_option.id, "value": "z", "color": "yellow"},
            {"value": "t", "color": "green"},
        ],
    )

    assert option_field.select_options.count() == 4
    user2_option_made_after_undo = option_field.select_options.filter(value="t").get()

    actions = ActionHandler.undo(
        user, [UpdateFieldActionType.scope(option_field.table_id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])
    # The second users option has been destroyed as the undo just restores the snapshot
    # of all previous select options.
    assert option_field.select_options.count() == 2
    assert list(
        option_field.select_options.values_list("value", flat=True)
    ) == unordered(["x", "y"])

    # Assert the row now shows no select option.
    assert list(model.objects.values_list("singleselect__value", flat=True)) == [
        "x",
        "y",
        None,
        None,
    ]

    # The second user then makes another select option after the undo.
    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user2,
        option_field,
        select_options=[
            {"id": option_a.id, "value": "x", "color": "blue"},
            {"id": option_b.id, "value": "y", "color": "red"},
            {"id": user2_option_made_after_undo.id, "value": "t", "color": "green"},
            {"value": "after_redo", "color": "green"},
        ],
    )
    assert option_field.select_options.count() == 4

    actions = ActionHandler.redo(
        user, [UpdateFieldActionType.scope(option_field.table_id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])

    # The first users new select option is added back
    assert list(
        option_field.select_options.values_list("value", flat=True)
    ) == unordered(["x", "y", "z", "t"])
    model = table.get_model(attribute_names=True)

    # The row shows the deleted select option again.
    assert list(model.objects.values_list("singleselect__value", flat=True)) == [
        "x",
        "y",
        None,
        "z",
    ]


@pytest.mark.django_db
@pytest.mark.undo_redo
@pytest.mark.field_single_select
def test_can_undo_redo_removing_select_option(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    user2 = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_user_workspace(
        user=user2, workspace=table.database.workspace, permissions="ADMIN"
    )

    option_field = data_fixture.create_single_select_field(
        user=user, table=table, name="singleselect"
    )
    option_a = data_fixture.create_select_option(
        field=option_field, value="x", color="blue"
    )
    option_b = data_fixture.create_select_option(
        field=option_field, value="y", color="red"
    )

    model = table.get_model(attribute_names=True)
    model.objects.bulk_create(
        [
            model(singleselect=option_a),
            model(singleselect=option_b),
            model(singleselect=None),
        ]
    )

    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user,
        option_field,
        select_options=[
            {"id": option_b.id, "value": "y", "color": "red"},
        ],
    )

    assert option_field.select_options.count() == 1

    assert list(model.objects.values_list("singleselect__value", flat=True)) == [
        None,
        "y",
        None,
    ]

    # The second user then makes their own select option.
    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user2,
        option_field,
        select_options=[
            {"id": option_b.id, "value": "y", "color": "red"},
            {"value": "t", "color": "green"},
        ],
    )

    assert option_field.select_options.count() == 2
    user2_option_made_after_undo = option_field.select_options.filter(value="t").get()

    actions = ActionHandler.undo(
        user, [UpdateFieldActionType.scope(option_field.table_id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])
    assert option_field.select_options.count() == 2
    # The first users new select option is added, and the one the second user made
    # has been destroyed by the snapshotting.
    assert list(
        option_field.select_options.values_list("value", flat=True)
    ) == unordered(["x", "y"])

    # Assert the row now shows the select option again.
    assert list(model.objects.values_list("singleselect__value", flat=True)) == [
        "x",
        "y",
        None,
    ]

    # The second user then makes another select option after the undo.
    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user2,
        option_field,
        select_options=[
            {"id": option_a.id, "value": "x", "color": "blue"},
            {"id": option_b.id, "value": "y", "color": "red"},
            {"id": user2_option_made_after_undo.id, "value": "t", "color": "green"},
            {"value": "after_redo", "color": "green"},
        ],
    )
    assert option_field.select_options.count() == 4

    actions = ActionHandler.redo(
        user, [UpdateFieldActionType.scope(option_field.table_id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])

    # The first users new select option is removed again
    assert list(
        option_field.select_options.values_list("value", flat=True)
    ) == unordered(["y", "t"])

    # The row no longer shows the deleted select option.
    assert list(model.objects.values_list("singleselect__value", flat=True)) == [
        None,
        "y",
        None,
    ]


@pytest.mark.django_db
@pytest.mark.undo_redo
@pytest.mark.field_single_select
def test_can_undo_redo_updating_single_select(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    user2 = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_user_workspace(
        user=user2, workspace=table.database.workspace, permissions="ADMIN"
    )

    option_field = data_fixture.create_single_select_field(
        user=user, table=table, name="singleselect"
    )
    option_a = data_fixture.create_select_option(
        field=option_field, value="x", color="blue"
    )
    option_b = data_fixture.create_select_option(
        field=option_field, value="y", color="red"
    )

    model = table.get_model(attribute_names=True)
    model.objects.bulk_create(
        [
            model(singleselect=option_a),
            model(singleselect=option_b),
            model(singleselect=None),
        ]
    )

    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user,
        option_field,
        select_options=[
            {"id": option_a.id, "value": "updated x", "color": "blue"},
            {"id": option_b.id, "value": "y", "color": "updated red"},
        ],
    )

    assert option_field.select_options.count() == 2

    assert list(model.objects.values_list("singleselect__value", flat=True)) == [
        "updated x",
        "y",
        None,
    ]

    # The second user then makes their own select option.
    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user2,
        option_field,
        select_options=[
            {"id": option_a.id, "value": "updated x", "color": "blue"},
            {"id": option_b.id, "value": "y", "color": "updated red"},
            {"value": "t", "color": "green"},
        ],
    )
    assert list(
        option_field.select_options.values_list("value", flat=True)
    ) == unordered(["updated x", "y", "t"])
    assert list(
        option_field.select_options.values_list("color", flat=True)
    ) == unordered(["blue", "updated red", "green"])

    assert option_field.select_options.count() == 3
    user2_option_made_after_undo = option_field.select_options.filter(value="t").get()

    actions = ActionHandler.undo(
        user, [UpdateFieldActionType.scope(option_field.table_id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])
    assert option_field.select_options.count() == 2

    assert list(
        option_field.select_options.values_list("value", flat=True)
    ) == unordered(["x", "y"])
    assert list(
        option_field.select_options.values_list("color", flat=True)
    ) == unordered(["blue", "red"])

    assert list(model.objects.values_list("singleselect__value", flat=True)) == [
        "x",
        "y",
        None,
    ]

    # The second user then makes another select option after the undo.
    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user2,
        option_field,
        select_options=[
            {"id": option_a.id, "value": "x", "color": "blue"},
            {"id": option_b.id, "value": "y", "color": "red"},
            {"id": user2_option_made_after_undo.id, "value": "t", "color": "green"},
            {"value": "after_redo", "color": "green"},
        ],
    )
    assert option_field.select_options.count() == 4

    actions = ActionHandler.redo(
        user, [UpdateFieldActionType.scope(option_field.table_id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])

    assert list(
        option_field.select_options.values_list("value", flat=True)
    ) == unordered(["updated x", "y", "t"])
    assert list(
        option_field.select_options.values_list("color", flat=True)
    ) == unordered(["blue", "updated red", "green"])

    assert list(model.objects.values_list("singleselect__value", flat=True)) == [
        "updated x",
        "y",
        None,
    ]


@pytest.mark.django_db
@pytest.mark.undo_redo
@pytest.mark.disabled_in_ci
def test_can_undo_updating_field_every_type(data_fixture, django_assert_num_queries):
    session_id = "session-id"

    table, user, row, _, context = setup_interesting_test_table(
        data_fixture, user_kwargs={"session_id": session_id}
    )
    model = table.get_model(attribute_names=True)
    model.objects.bulk_create(
        [
            model(),
        ]
    )
    for field_object in model._field_objects.values():
        field = field_object["field"]
        field_type = field_object["type"]
        if field_type.type == "link_row" or "select" in field_type.type:
            continue
        before_serialized = field_type.export_serialized(field)
        action_type_registry.get_by_type(UpdateFieldActionType).do(
            user, field, new_type_name="number"
        )
        actions = ActionHandler.undo(
            user, [UpdateFieldActionType.scope(field.table_id)], session_id
        )
        assert_undo_redo_actions_are_valid(
            actions, [UpdateFieldActionType]
        ), f"Failed for {before_serialized}"
        new_field = FieldHandler().get_specific_field_for_update(field.id)
        after_serialized = field_type.export_serialized(new_field)
        assert before_serialized == after_serialized


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_updating_max_value_of_rating_field(
    data_fixture, django_assert_num_queries
):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    original_text_default = "text_default"
    original_max_value = 10
    field = data_fixture.create_rating_field(
        user=user, name="field", max_value=original_max_value
    )
    model = field.table.get_model(attribute_names=True)
    model.objects.bulk_create(
        [
            model(field=10),
            model(field=9),
            model(field=8),
            model(field=1),
        ]
    )

    action_type_registry.get_by_type(UpdateFieldActionType).do(user, field, max_value=2)
    model = field.table.get_model(attribute_names=True)

    assert list(model.objects.values_list("field", flat=True)) == [
        Decimal("2"),
        Decimal("2"),
        Decimal("2"),
        Decimal("1"),
    ]

    actions = ActionHandler.undo(
        user, [UpdateFieldActionType.scope(field.table_id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])

    undone_field = FieldHandler().get_field(field.id, RatingField)
    assert undone_field.max_value == original_max_value

    model = field.table.get_model(attribute_names=True)
    assert list(model.objects.values_list("field", flat=True)) == [
        10,
        9,
        8,
        1,
    ]

    actions = ActionHandler.redo(
        user, [UpdateFieldActionType.scope(field.table_id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])

    assert list(model.objects.values_list("field", flat=True)) == [
        Decimal("2"),
        Decimal("2"),
        Decimal("2"),
        Decimal("1"),
    ]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_duplicate_fields_of_interesting_table(api_client, data_fixture):
    session_id = "session-id"
    user, token = data_fixture.create_user_and_token(session_id=session_id)
    database = data_fixture.create_database_application(user=user)
    field_handler = FieldHandler()

    table, _, _, _, _ = setup_interesting_test_table(data_fixture, user, database)
    original_field_set = list(table.field_set.all())

    duplicated_fields = {}
    for field in original_field_set:
        duplicated_field, _ = action_type_registry.get_by_type(
            DuplicateFieldActionType
        ).do(user, field.specific, duplicate_data=True)
        duplicated_fields[field.id] = duplicated_field

        assert field_handler.get_field(duplicated_field.id).name == f"{field.name} 2"

        actions_undone = ActionHandler.undo(
            user, [DuplicateFieldActionType.scope(table_id=field.table_id)], session_id
        )

        assert_undo_redo_actions_are_valid(actions_undone, [DuplicateFieldActionType])
        with pytest.raises(FieldDoesNotExist):
            field_handler.get_field(duplicated_field.id)

        actions_redone = ActionHandler.redo(
            user, [DuplicateFieldActionType.scope(table_id=field.table_id)], session_id
        )

        assert_undo_redo_actions_are_valid(actions_redone, [DuplicateFieldActionType])
        assert field_handler.get_field(duplicated_field.id).name == f"{field.name} 2"

    # check that the field values have been duplicated correctly
    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json["results"]) > 0
    assert table.field_set.count() == len(original_field_set) * 2
    for row in response_json["results"]:
        for field in original_field_set:
            row_1_value = extract_serialized_field_value(row[field.db_column])
            duplicated_field = duplicated_fields[field.id]
            row_2_value = extract_serialized_field_value(
                row[duplicated_field.db_column]
            )
            assert_serialized_field_values_are_the_same(
                row_1_value,
                row_2_value,
                field_name=field.name,
            )


@pytest.mark.django_db
def test_date_field_type_undo_redo_fix_timezone_offset(api_client, data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(user=user)
    datetime_field = data_fixture.create_date_field(table=table, date_include_time=True)
    table_model = table.get_model()

    row_1 = table_model.objects.create(
        **{f"field_{datetime_field.id}": "2022-01-01 00:00Z"}
    )
    row_2 = table_model.objects.create(
        **{f"field_{datetime_field.id}": "2022-01-01 23:30Z"}
    )
    row_3 = table_model.objects.create(
        **{f"field_{datetime_field.id}": "2022-01-02 15:00Z"}
    )
    row_1.refresh_from_db()
    row_2.refresh_from_db()
    row_3.refresh_from_db()
    original_datetime_1 = getattr(row_1, f"field_{datetime_field.id}")
    original_datetime_2 = getattr(row_2, f"field_{datetime_field.id}")
    original_datetime_3 = getattr(row_3, f"field_{datetime_field.id}")

    utc_offset = 60
    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user,
        datetime_field,
        name="test",
        date_force_timezone="Europe/Rome",
        date_force_timezone_offset=utc_offset,
    )

    def row_datetime_updated(row):
        prev_datetime = getattr(row, f"field_{datetime_field.id}")
        row.refresh_from_db()
        new_datetime = getattr(row, f"field_{datetime_field.id}")
        return new_datetime == (prev_datetime + timedelta(minutes=utc_offset))

    # all the rows has been updated, adding 60 minutes to the time
    assert row_datetime_updated(row_1)
    assert row_datetime_updated(row_2)
    assert row_datetime_updated(row_3)

    actions = ActionHandler.undo(
        user, [UpdateFieldActionType.scope(table_id=table.id)], session_id
    )
    assert len(actions) == 1
    assert actions[0].type == UpdateFieldActionType.type

    utc_offset = -utc_offset
    assert row_datetime_updated(row_1)
    assert row_datetime_updated(row_2)
    assert row_datetime_updated(row_3)
    assert getattr(row_1, f"field_{datetime_field.id}") == original_datetime_1
    assert getattr(row_2, f"field_{datetime_field.id}") == original_datetime_2
    assert getattr(row_3, f"field_{datetime_field.id}") == original_datetime_3

    actions = ActionHandler.redo(
        user, [UpdateFieldActionType.scope(table_id=table.id)], session_id
    )
    assert len(actions) == 1
    assert actions[0].type == UpdateFieldActionType.type

    utc_offset = -utc_offset
    assert row_datetime_updated(row_1)
    assert row_datetime_updated(row_2)
    assert row_datetime_updated(row_3)
    assert getattr(
        row_1, f"field_{datetime_field.id}"
    ) == original_datetime_1 + timedelta(minutes=utc_offset)
    assert getattr(
        row_2, f"field_{datetime_field.id}"
    ) == original_datetime_2 + timedelta(minutes=utc_offset)
    assert getattr(
        row_3, f"field_{datetime_field.id}"
    ) == original_datetime_3 + timedelta(minutes=utc_offset)


@pytest.mark.django_db
@pytest.mark.undo_redo
@pytest.mark.field_single_select
def test_can_undo_redo_change_primary_field(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table_a = data_fixture.create_database_table(user)
    field_1 = data_fixture.create_text_field(user=user, primary=True, table=table_a)
    field_2 = data_fixture.create_text_field(user=user, primary=False, table=table_a)

    new_primary_field, old_primary_field = action_type_registry.get_by_type(
        ChangePrimaryFieldActionType
    ).do(user, table_a, field_2)

    assert new_primary_field.id == field_2.id
    assert old_primary_field.id == field_1.id

    field_1.refresh_from_db()
    field_2.refresh_from_db()
    assert field_1.primary is False
    assert field_2.primary is True

    actions = ActionHandler.undo(
        user, [ChangePrimaryFieldActionType.scope(table_a.id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [ChangePrimaryFieldActionType])

    field_1.refresh_from_db()
    field_2.refresh_from_db()
    assert field_1.primary is True
    assert field_2.primary is False

    actions = ActionHandler.redo(
        user, [ChangePrimaryFieldActionType.scope(table_a.id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [ChangePrimaryFieldActionType])

    field_1.refresh_from_db()
    field_2.refresh_from_db()
    assert field_1.primary is False
    assert field_2.primary is True


@pytest.mark.django_db
@pytest.mark.undo_redo
@pytest.mark.field_single_select
def test_undo_single_select_conversion_with_default_value(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)

    option_field = data_fixture.create_single_select_field(user=user, name="priority")
    option_a = data_fixture.create_select_option(
        field=option_field, value="High", color="red"
    )

    field_handler = FieldHandler()
    option_field = field_handler.update_field(
        user=user, field=option_field, single_select_default=option_a.id
    )

    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user,
        option_field,
        select_options=[
            {"value": "Low", "color": "green"},
            {"value": "Medium", "color": "yellow"},
        ],
        single_select_default=None,
    )

    option_field.refresh_from_db()
    assert option_field.select_options.count() == 2
    assert option_field.single_select_default is None

    actions = ActionHandler.undo(
        user, [UpdateFieldActionType.scope(option_field.table_id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])

    option_field.refresh_from_db()
    assert option_field.select_options.count() == 1
    restored_option = option_field.select_options.first()
    assert restored_option.value == "High"
    assert restored_option.color == "red"
    assert option_field.single_select_default == restored_option.id


@pytest.mark.django_db
@pytest.mark.undo_redo
@pytest.mark.field_multiple_select  # Fix the decorator
def test_undo_multiple_select_conversion_with_default_value(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)

    option_field = data_fixture.create_multiple_select_field(user=user, name="tags")
    option_a = data_fixture.create_select_option(
        field=option_field, value="Important", color="red"
    )
    option_b = data_fixture.create_select_option(
        field=option_field, value="Urgent", color="blue"
    )

    field_handler = FieldHandler()
    option_field = field_handler.update_field(
        user=user,
        field=option_field,
        multiple_select_default=[option_a.id, option_b.id],
    )

    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user,
        option_field,
        select_options=[
            {"value": "Low", "color": "green"},
            {"value": "Medium", "color": "yellow"},
        ],
        multiple_select_default=None,
    )

    option_field.refresh_from_db()
    assert option_field.select_options.count() == 2
    assert option_field.multiple_select_default == []

    actions = ActionHandler.undo(
        user, [UpdateFieldActionType.scope(option_field.table_id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions, [UpdateFieldActionType])

    option_field.refresh_from_db()
    assert option_field.select_options.count() == 2
    restored_options = list(option_field.select_options.all())

    restored_values = [opt.value for opt in restored_options]
    assert "Important" in restored_values
    assert "Urgent" in restored_values

    restored_ids = [opt.id for opt in restored_options]
    assert set(option_field.multiple_select_default) == set(restored_ids)
