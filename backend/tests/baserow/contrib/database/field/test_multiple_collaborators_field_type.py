import os
from io import BytesIO

from django.apps.registry import apps
from django.contrib.auth import get_user_model

import pytest
from faker import Faker

from baserow.contrib.database.fields.field_types import MultipleCollaboratorsFieldType
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import MultipleCollaboratorsField
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.views.handler import ViewHandler
from baserow.core.handler import CoreHandler
from baserow.core.models import WORKSPACE_USER_PERMISSION_ADMIN, WorkspaceUser
from baserow.core.registries import ImportExportConfig
from baserow.test_utils.helpers import AnyInt

User = get_user_model()


@pytest.mark.django_db
@pytest.mark.field_multiple_collaborators
def test_multiple_collaborators_field_type_create(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)

    row_handler = RowHandler()

    collaborator_field = data_fixture.create_multiple_collaborators_field(
        user=user, table=table, name="Collaborator 1"
    )
    field_id = collaborator_field.db_column

    assert MultipleCollaboratorsField.objects.all().first().id == collaborator_field.id

    row = row_handler.create_row(
        user=user, table=table, values={field_id: [{"id": user.id}]}
    )
    assert row.id
    collaborator_field_list = getattr(row, field_id).all()
    assert len(collaborator_field_list) == 1
    assert collaborator_field_list[0].id == user.id


@pytest.mark.django_db
@pytest.mark.field_multiple_collaborators
def test_multiple_collaborators_field_type_update(data_fixture):
    workspace = data_fixture.create_workspace()
    user = data_fixture.create_user(workspace=workspace)
    user2 = data_fixture.create_user(workspace=workspace)
    user3 = data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(
        user=user, name="Placeholder", workspace=workspace
    )
    table = data_fixture.create_database_table(name="Example", database=database)

    row_handler = RowHandler()

    collaborator_field = data_fixture.create_multiple_collaborators_field(
        user=user, table=table, name="Collaborator 1"
    )
    field_id = collaborator_field.db_column

    assert MultipleCollaboratorsField.objects.all().first().id == collaborator_field.id

    row = row_handler.create_row(user=user, table=table, values={field_id: []})

    row_handler.update_row(
        user, table, row, {field_id: [{"id": user2.id}, {"id": user3.id}]}
    )

    collaborator_field_list = getattr(row, field_id).all().order_by("id")
    assert len(collaborator_field_list) == 2
    assert collaborator_field_list[0].id == user2.id
    assert collaborator_field_list[1].id == user3.id


@pytest.mark.django_db(transaction=True)
def test_get_set_export_serialized_value_multiple_collaborators_field(data_fixture):
    user = data_fixture.create_user(email="user1@baserow.io")
    user_2 = data_fixture.create_user(email="user2@baserow.io")
    user_3 = data_fixture.create_user(email="user3@baserow.io")
    workspace = data_fixture.create_workspace(user=user)
    data_fixture.create_user_workspace(workspace=workspace, user=user_2)
    data_fixture.create_user_workspace(workspace=workspace, user=user_3)

    imported_workspace = data_fixture.create_workspace(user=user)
    data_fixture.create_user_workspace(workspace=imported_workspace, user=user_2)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    row_handler = RowHandler()
    core_handler = CoreHandler()

    multiple_collaborators__field = data_fixture.create_multiple_collaborators_field(
        user=user, table=table, name="Multiple collaborators"
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={},
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{multiple_collaborators__field.id}": [
                {"id": user.id},
                {"id": user_2.id},
            ],
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        values={
            f"field_{multiple_collaborators__field.id}": [
                {"id": user.id},
                {"id": user_3.id},
            ],
        },
    )

    config = ImportExportConfig(include_permission_data=False)
    exported_applications = core_handler.export_workspace_applications(
        workspace, BytesIO(), config
    )
    imported_applications, id_mapping = core_handler.import_applications_to_workspace(
        imported_workspace, exported_applications, BytesIO(), config, None
    )
    imported_database = imported_applications[0]
    imported_table = imported_database.table_set.all()[0]
    imported_field = imported_table.field_set.all().first().specific

    assert imported_table.id != table.id
    assert imported_field.id != multiple_collaborators__field.id

    imported_model = imported_table.get_model()
    all = imported_model.objects.all()
    assert len(all) == 3
    imported_row_1 = all[0]
    imported_row_1_field = (
        getattr(imported_row_1, f"field_" f"{imported_field.id}").order_by("id").all()
    )
    imported_row_2 = all[1]
    imported_row_2_field = (
        getattr(imported_row_2, f"field_{imported_field.id}").order_by("id").all()
    )
    imported_row_3 = all[2]
    imported_row_3_field = (
        getattr(imported_row_3, f"field_{imported_field.id}").order_by("id").all()
    )

    assert len(imported_row_1_field) == 0
    assert len(imported_row_2_field) == 2
    assert imported_row_2_field[0].id == user.id
    assert imported_row_2_field[1].id == user_2.id
    assert len(imported_row_3_field) == 1
    assert imported_row_3_field[0].id == user.id


@pytest.mark.django_db
def test_multiple_collaborators_field_type_sorting(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user(email="user1@baserow.io", first_name="User 1")
    user_2 = data_fixture.create_user(email="user2@baserow.io", first_name="User 2")
    user_3 = data_fixture.create_user(email="user3@baserow.io", first_name="User 3")
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    data_fixture.create_user_workspace(workspace=database.workspace, user=user_2)
    data_fixture.create_user_workspace(workspace=database.workspace, user=user_3)
    table = data_fixture.create_database_table(name="Example", database=database)
    grid_view = data_fixture.create_grid_view(table=table)

    view_handler = ViewHandler()

    field = data_fixture.create_multiple_collaborators_field(
        user=user, table=table, name="Multiple Collaborators"
    )

    row_1 = data_fixture.create_row_for_many_to_many_field(
        table=table,
        field=field,
        values=[{"id": user.id}, {"id": user_2.id}, {"id": user_3.id}],
        user=user,
    )
    row_2 = data_fixture.create_row_for_many_to_many_field(
        table=table,
        field=field,
        values=[{"id": user_3.id}, {"id": user_2.id}, {"id": user.id}],
        user=user,
    )
    row_3 = data_fixture.create_row_for_many_to_many_field(
        table=table, field=field, values=[{"id": user_3.id}, {"id": user.id}], user=user
    )
    row_4 = data_fixture.create_row_for_many_to_many_field(
        table=table, field=field, values=[{"id": user_2.id}], user=user
    )
    row_5 = data_fixture.create_row_for_many_to_many_field(
        table=table, field=field, values=[], user=user
    )

    sort = data_fixture.create_view_sort(view=grid_view, field=field, order="ASC")
    model = table.get_model()
    rows = view_handler.apply_sorting(grid_view, model.objects.all())
    row_ids = [row.id for row in rows]
    assert row_ids == [row_5.id, row_1.id, row_4.id, row_3.id, row_2.id]

    sort.order = "DESC"
    sort.save()

    rows = view_handler.apply_sorting(grid_view, model.objects.all())
    row_ids = [row.id for row in rows]
    assert row_ids == [row_2.id, row_3.id, row_4.id, row_1.id, row_5.id]


@pytest.mark.django_db
def test_call_apps_registry_pending_operations(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    table = data_fixture.create_database_table(name="Example", database=database)

    data_fixture.create_multiple_collaborators_field(
        user=user, table=table, name="Test"
    )
    table.get_model()
    # Make sure that there are no pending operations in the app registry. Because a
    # Django ManyToManyField registers pending operations every time a table model is
    # generated, which can causes a memory leak if they are not triggered.
    assert len(apps._pending_operations) == 0


@pytest.mark.django_db
def test_multiple_collaborators_model_field(data_fixture):
    user = data_fixture.create_user(email="user1@baserow.io", first_name="User 1")
    user_2 = data_fixture.create_user(email="user2@baserow.io", first_name="User 2")
    user_3 = data_fixture.create_user(email="user3@baserow.io", first_name="User 3")
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    data_fixture.create_user_workspace(workspace=database.workspace, user=user_2)
    workspace_user_3 = data_fixture.create_user_workspace(
        workspace=database.workspace, user=user_3
    )
    table = data_fixture.create_database_table(name="Example", database=database)

    field = data_fixture.create_multiple_collaborators_field(
        user=user, table=table, name="Multiple Collaborators"
    )

    data_fixture.create_row_for_many_to_many_field(
        table=table,
        field=field,
        values=[{"id": user.id}, {"id": user_2.id}],
        user=user,
    )
    data_fixture.create_row_for_many_to_many_field(
        table=table,
        field=field,
        values=[{"id": user_2.id}, {"id": user_3.id}],
        user=user,
    )
    data_fixture.create_row_for_many_to_many_field(
        table=table,
        field=field,
        values=[{"id": user_3.id}, {"id": user_2.id}, {"id": user.id}],
        user=user,
    )

    model = table.get_model()
    rows = list(model.objects.all().order_by("id"))

    row_1_relations = getattr(rows[0], f"field_{field.id}").all()
    row_1_relation_ids = [u.id for u in row_1_relations]
    assert row_1_relation_ids == [user.id, user_2.id]

    row_2_relations = getattr(rows[1], f"field_{field.id}").all()
    row_2_relation_ids = [u.id for u in row_2_relations]
    assert row_2_relation_ids == [user_2.id, user_3.id]

    row_3_relations = getattr(rows[2], f"field_{field.id}").all()
    row_3_relation_ids = [u.id for u in row_3_relations]
    assert row_3_relation_ids == [user_3.id, user_2.id, user.id]

    # After deleting workspace user 3, we don't expect user_3 to be returned here
    # anymore.
    workspace_user_3.delete()

    rows = list(model.objects.all().order_by("id"))

    row_1_relations = getattr(rows[0], f"field_{field.id}").all()
    row_1_relation_ids = [u.id for u in row_1_relations]
    assert row_1_relation_ids == [user.id, user_2.id]

    row_2_relations = getattr(rows[1], f"field_{field.id}").all()
    row_2_relation_ids = [u.id for u in row_2_relations]
    assert row_2_relation_ids == [user_2.id]

    row_3_relations = getattr(rows[2], f"field_{field.id}").all()
    row_3_relation_ids = [u.id for u in row_3_relations]
    assert row_3_relation_ids == [user_2.id, user.id]


@pytest.mark.django_db
def test_multiple_collaborators_model_enhanced_field(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user(email="user1@baserow.io", first_name="User 1")
    user_2 = data_fixture.create_user(email="user2@baserow.io", first_name="User 2")
    user_3 = data_fixture.create_user(email="user3@baserow.io", first_name="User 3")
    database = data_fixture.create_database_application(user=user, name="Placeholder")
    data_fixture.create_user_workspace(workspace=database.workspace, user=user_2)
    workspace_user_3 = data_fixture.create_user_workspace(
        workspace=database.workspace, user=user_3
    )
    table = data_fixture.create_database_table(name="Example", database=database)
    field = data_fixture.create_multiple_collaborators_field(
        user=user, table=table, name="Multiple Collaborators"
    )

    data_fixture.create_row_for_many_to_many_field(
        table=table,
        field=field,
        values=[{"id": user.id}, {"id": user_2.id}],
        user=user,
    )
    data_fixture.create_row_for_many_to_many_field(
        table=table,
        field=field,
        values=[{"id": user_2.id}, {"id": user_3.id}],
        user=user,
    )
    data_fixture.create_row_for_many_to_many_field(
        table=table,
        field=field,
        values=[{"id": user_3.id}, {"id": user_2.id}, {"id": user.id}],
        user=user,
    )

    model = table.get_model()

    with django_assert_num_queries(2):
        rows = list(model.objects.all().order_by("id").enhance_by_fields())

        row_1_relations = getattr(rows[0], f"field_{field.id}").all()
        row_1_relation_ids = [u.id for u in row_1_relations]
        assert row_1_relation_ids == [user.id, user_2.id]

        row_2_relations = getattr(rows[1], f"field_{field.id}").all()
        row_2_relation_ids = [u.id for u in row_2_relations]
        assert row_2_relation_ids == [user_2.id, user_3.id]

        row_3_relations = getattr(rows[2], f"field_{field.id}").all()
        row_3_relation_ids = [u.id for u in row_3_relations]
        assert row_3_relation_ids == [user_3.id, user_2.id, user.id]

    # After deleting workspace user 3, we don't expect user_3 to be
    # returned here anymore.
    workspace_user_3.delete()

    with django_assert_num_queries(2):
        rows = list(model.objects.all().order_by("id").enhance_by_fields())

        row_1_relations = getattr(rows[0], f"field_{field.id}").all()
        row_1_relation_ids = [u.id for u in row_1_relations]
        assert row_1_relation_ids == [user.id, user_2.id]

        row_2_relations = getattr(rows[1], f"field_{field.id}").all()
        row_2_relation_ids = [u.id for u in row_2_relations]
        assert row_2_relation_ids == [user_2.id]

        row_3_relations = getattr(rows[2], f"field_{field.id}").all()
        row_3_relation_ids = [u.id for u in row_3_relations]
        assert row_3_relation_ids == [user_2.id, user.id]


@pytest.mark.django_db
def test_multiple_collaborators_field_type_random_value(data_fixture):
    workspace = data_fixture.create_workspace()
    user = data_fixture.create_user(workspace=workspace)
    user2 = data_fixture.create_user(workspace=workspace)
    user3 = data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(
        user=user, workspace=workspace, name="database"
    )
    table = data_fixture.create_database_table(name="table", database=database)
    cache = {}
    fake = Faker()

    field = data_fixture.create_multiple_collaborators_field(
        user=user, table=table, name="Multiple collaborators"
    )

    possible_collaborators = [user, user2, user3]
    random_choice = MultipleCollaboratorsFieldType().random_value(field, fake, cache)
    assert type(random_choice) is list
    assert (
        set([x.id for x in possible_collaborators]).issuperset(set(random_choice))
        is True
    )

    random_choice = MultipleCollaboratorsFieldType().random_value(field, fake, cache)
    assert type(random_choice) is list
    assert (
        set([x.id for x in possible_collaborators]).issuperset(set(random_choice))
        is True
    )


@pytest.mark.django_db
def test_multiple_collaborators_field_adjacent_row(data_fixture):
    workspace = data_fixture.create_workspace()
    user = data_fixture.create_user(workspace=workspace, first_name="User 1")
    user_2 = data_fixture.create_user(workspace=workspace, first_name="User 2")
    user_3 = data_fixture.create_user(workspace=workspace, first_name="User 3")
    database = data_fixture.create_database_application(
        user=user, workspace=workspace, name="database"
    )
    table = data_fixture.create_database_table(name="table", database=database)
    grid_view = data_fixture.create_grid_view(table=table)

    field = data_fixture.create_multiple_collaborators_field(
        user=user, table=table, name="Multiple collaborators"
    )

    data_fixture.create_view_sort(view=grid_view, field=field, order="DESC")

    row_a = data_fixture.create_row_for_many_to_many_field(
        table=table,
        field=field,
        values=[{"id": user.id}],
        user=user,
    )
    row_b = data_fixture.create_row_for_many_to_many_field(
        table=table,
        field=field,
        values=[{"id": user_2.id}],
        user=user,
    )
    row_c = data_fixture.create_row_for_many_to_many_field(
        table=table,
        field=field,
        values=[{"id": user_3.id}],
        user=user,
    )

    table_model = table.get_model()
    previous_row = RowHandler().get_adjacent_row(
        table_model, row_b.id, previous=True, view=grid_view
    )
    next_row = RowHandler().get_adjacent_row(table_model, row_b.id, view=grid_view)

    assert previous_row.id == row_c.id
    assert next_row.id == row_a.id


@pytest.mark.django_db
@pytest.mark.field_multiple_collaborators
@pytest.mark.row_history
def test_multiple_collaborators_serialize_metadata_for_row_history(
    data_fixture, django_assert_num_queries
):
    workspace = data_fixture.create_workspace()
    database = data_fixture.create_database_application(workspace=workspace)
    user = data_fixture.create_user(workspace=workspace)
    user2 = data_fixture.create_user(workspace=workspace)
    user3 = data_fixture.create_user(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    field_handler = FieldHandler()
    field = field_handler.create_field(
        user=user,
        table=table,
        type_name="multiple_collaborators",
        name="Multiple collaborators",
    )
    model = table.get_model()
    row_handler = RowHandler()
    original_row = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{field.id}": [
                {"id": user.id},
                {"id": user2.id},
            ],
        },
    )
    original_row = model.objects.all().enhance_by_fields().get(id=original_row.id)

    with django_assert_num_queries(0):
        metadata = MultipleCollaboratorsFieldType().serialize_metadata_for_row_history(
            field, original_row, None
        )

    getattr(original_row, f"field_{field.id}").set([user2.id, user3.id], clear=True)
    updated_row = model.objects.all().enhance_by_fields().get(id=original_row.id)

    with django_assert_num_queries(0):
        metadata = MultipleCollaboratorsFieldType().serialize_metadata_for_row_history(
            field, updated_row, metadata
        )

        assert metadata == {
            "id": AnyInt(),
            "collaborators": {
                user.id: {
                    "id": user.id,
                    "name": user.first_name,
                },
                user2.id: {
                    "id": user2.id,
                    "name": user2.first_name,
                },
                user3.id: {
                    "id": user3.id,
                    "name": user3.first_name,
                },
            },
            "type": "multiple_collaborators",
        }

    # empty values
    original_row = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={f"field_{field.id}": []},
    )
    original_row = model.objects.all().enhance_by_fields().get(id=original_row.id)

    with django_assert_num_queries(0):
        assert MultipleCollaboratorsFieldType().serialize_metadata_for_row_history(
            field, original_row, None
        ) == {
            "id": AnyInt(),
            "collaborators": {},
            "type": "multiple_collaborators",
        }


@pytest.mark.django_db
@pytest.mark.field_multiple_collaborators
@pytest.mark.row_history
def test_multiple_collaborators_are_row_values_equal(
    data_fixture, django_assert_num_queries
):
    workspace = data_fixture.create_workspace()
    user = data_fixture.create_user(workspace=workspace)
    user2 = data_fixture.create_user(workspace=workspace)
    user3 = data_fixture.create_user(workspace=workspace)

    with django_assert_num_queries(0):
        assert (
            MultipleCollaboratorsFieldType().are_row_values_equal(
                [{"id": user3.id}], [{"id": user3.id}]
            )
            is True
        )

        assert (
            MultipleCollaboratorsFieldType().are_row_values_equal(
                [{"id": user.id}, {"id": user2.id}], [{"id": user2.id}, {"id": user.id}]
            )
            is True
        )

        assert MultipleCollaboratorsFieldType().are_row_values_equal([], []) is True

        assert (
            MultipleCollaboratorsFieldType().are_row_values_equal([], [{"id": user.id}])
            is False
        )

        assert (
            MultipleCollaboratorsFieldType().are_row_values_equal(
                [{"id": user.id}, {"id": user2.id}], [{"id": user.id}, {"id": user3.id}]
            )
            is False
        )


@pytest.mark.django_db
def test_multiple_collaborators_field_type_get_order_collate(data_fixture):
    workspace = data_fixture.create_workspace()
    user = data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    multiple_collaborators_field = data_fixture.create_multiple_collaborators_field(
        table=table, name="field", order=1, primary=True
    )

    model = table.get_model()

    dir_path = os.path.dirname(os.path.realpath(__file__))
    with open(
        dir_path + "/../../../../../../tests/all_chars.txt", mode="r", encoding="utf-8"
    ) as f:
        all_chars = f.read()
    with open(
        dir_path + "/../../../../../../tests/sorted_chars.txt",
        mode="r",
        encoding="utf-8",
    ) as f:
        sorted_chars = f.read()

    users, rows = [], []
    for char in all_chars:
        email = data_fixture.fake.unique.email()
        users.append(User(first_name=char, username=email, email=email))
        rows.append(model())

    users = User.objects.bulk_create(users)
    rows = model.objects.bulk_create(rows)

    workspace_users = []
    for user in users:
        workspace_users.append(
            WorkspaceUser(
                workspace=workspace,
                user=user,
                order=0,
                permissions=WORKSPACE_USER_PERMISSION_ADMIN,
            )
        )
    WorkspaceUser.objects.bulk_create(workspace_users)

    relations = []
    field_name = f"field_{multiple_collaborators_field.id}"

    for row, user in zip(rows, users):
        relation, _ = RowHandler()._prepare_m2m_field_related_objects(
            row, field_name, [user.id]
        )
        relations.extend(relation)

    getattr(model, field_name).through.objects.bulk_create(relations)

    queryset = (
        model.objects.all()
        .order_by_fields_string(field_name)
        .prefetch_related(field_name)
    )
    result = ""
    for char in queryset:
        all_collaborators = list(getattr(char, field_name).all())
        result += all_collaborators[0].first_name

    assert result == sorted_chars
