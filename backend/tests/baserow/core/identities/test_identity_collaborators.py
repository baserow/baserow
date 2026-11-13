from django.urls import reverse

import pytest

from baserow.contrib.database.api.fields.serializers import (
    AvailableCollaboratorsSerializer,
)
from baserow.contrib.database.fields.actions import UpdateFieldActionType
from baserow.contrib.database.fields.exceptions import (
    AllProvidedCollaboratorIdsMustBeValidUsers,
)
from baserow.contrib.database.fields.field_types import MultipleCollaboratorsFieldType
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.views.models import ViewDefaultValue
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.handler import CoreHandler
from baserow.core.identities.handler import IdentityHandler
from baserow.core.notifications.models import NotificationRecipient
from baserow.core.trash.handler import TrashHandler


@pytest.fixture
def collaborators(data_fixture):
    person = data_fixture.create_user(first_name="Person", session_id="session")
    table = data_fixture.create_database_table(user=person)
    identity = data_fixture.create_identity(
        workspace=table.database.workspace, name="Ops"
    )
    field = data_fixture.create_multiple_collaborators_field(
        table=table, notify_user_when_added=True, include_identities=True
    )
    return person, table, identity, field


def assigned_ids(table, field, row):
    """The users stored for the cell, whether or not a read would show them."""

    through = table.get_model()._meta.get_field(field.db_column).remote_field.through
    user_column = through._meta.get_fields()[2].attname
    return set(
        through.objects.filter(
            **{through._meta.get_fields()[1].attname: row.id}
        ).values_list(user_column, flat=True)
    )


@pytest.mark.django_db
def test_identities_are_not_collaborators_unless_the_field_includes_them(
    data_fixture, collaborators
):
    person, table, identity, _ = collaborators
    field = data_fixture.create_multiple_collaborators_field(table=table)
    field_type = MultipleCollaboratorsFieldType()

    assert not field.include_identities
    assert list(
        CoreHandler().get_workspace_collaborators(table.database.workspace)
    ) == [person]
    with pytest.raises(AllProvidedCollaboratorIdsMustBeValidUsers):
        field_type.prepare_value_for_db(field, [{"id": identity.id}])
    with pytest.raises(AllProvidedCollaboratorIdsMustBeValidUsers):
        field_type.prepare_value_for_db_in_bulk(field, {0: [{"id": identity.id}]})
    assert AvailableCollaboratorsSerializer(
        include_identities_source="include_identities"
    ).to_representation(field) == [
        {"id": person.id, "name": "Person", "user_type": "human"}
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("state", ["inactive", "trashed", "other_workspace"])
def test_a_field_that_includes_identities_rejects_unavailable_ones(
    data_fixture, collaborators, state
):
    _, _, identity, field = collaborators
    if state == "inactive":
        identity.is_active = False
        identity.save(update_fields=["is_active"])
    elif state == "trashed":
        identity.profile.trashed = True
        identity.profile.save(update_fields=["trashed"])
    else:
        identity = data_fixture.create_identity()

    with pytest.raises(AllProvidedCollaboratorIdsMustBeValidUsers):
        MultipleCollaboratorsFieldType().prepare_value_for_db(
            field, [{"id": identity.id}]
        )


@pytest.mark.django_db
def test_assigned_identity_is_shown_never_notified_and_hidden_while_trashed(
    collaborators,
):
    person, table, identity, field = collaborators
    row = RowHandler().create_row(
        person, table, {field.id: [{"id": identity.id}, {"id": person.id}]}
    )
    model = table.get_model()

    def shown():
        cell = getattr(model.objects.get(id=row.id), field.db_column)
        return set(cell.values_list("id", flat=True))

    assert shown() == {identity.id, person.id}
    assert not NotificationRecipient.objects.filter(recipient_id=identity.id).exists()
    assert AvailableCollaboratorsSerializer(
        include_identities_source="include_identities"
    ).to_representation(field) == [
        {"id": person.id, "name": "Person", "user_type": "human"},
        {"id": identity.id, "name": "Ops", "user_type": "identity"},
    ]

    IdentityHandler().delete_identity(person, identity)
    assert shown() == {person.id}
    TrashHandler.restore_item(person, "identity", identity.profile.id)
    assert shown() == {identity.id, person.id}


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_excluding_identities_deletes_their_values_and_undo_restores_them(
    data_fixture, collaborators
):
    person, table, identity, field = collaborators
    view = data_fixture.create_grid_view(table=table)
    view_default = ViewDefaultValue.objects.create(
        view=view,
        field=field,
        enabled=True,
        value=[{"id": identity.id}, {"id": person.id}],
    )
    count = FieldHandler().create_field(
        person, table, "formula", name="Count", formula=f"count(field('{field.name}'))"
    )
    row = RowHandler().create_row(
        person, table, {field.id: [{"id": identity.id}, {"id": person.id}]}
    )

    def counted():
        return getattr(table.get_model().objects.get(id=row.id), count.db_column)

    assert counted() == 2

    action_type_registry.get_by_type(UpdateFieldActionType).do(
        person, field, include_identities=False
    )

    field.refresh_from_db()
    assert not field.include_identities
    assert assigned_ids(table, field, row) == {person.id}
    assert counted() == 1
    view_default.refresh_from_db()
    assert view_default.value == [{"id": person.id}]

    ActionHandler.undo(person, [UpdateFieldActionType.scope(table.id)], "session")

    field.refresh_from_db()
    assert field.include_identities
    assert assigned_ids(table, field, row) == {identity.id, person.id}
    assert counted() == 2


@pytest.mark.django_db
def test_field_list_returns_identity_collaborators_with_constant_queries(
    collaborators, data_fixture, api_client, django_assert_max_num_queries
):
    person, table, identity, field = collaborators
    token = data_fixture.generate_token(person)
    url = reverse("api:database:fields:list", kwargs={"table_id": table.id})

    def list_fields():
        return api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}").json()

    available = next(f for f in list_fields() if f["id"] == field.id)
    assert available["include_identities"]
    assert {
        (c["id"], c["user_type"]) for c in available["available_collaborators"]
    } == {
        (person.id, "human"),
        (identity.id, "identity"),
    }

    with django_assert_max_num_queries(40) as queries:
        list_fields()
    for _ in range(3):
        data_fixture.create_identity(workspace=table.database.workspace)
    with django_assert_max_num_queries(len(queries)):
        list_fields()
