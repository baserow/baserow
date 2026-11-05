from django.core.exceptions import ValidationError
from django.db import connection

import pytest

from baserow.contrib.database.api.fields.serializers import CollaboratorSerializer
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.agents.handler import AgentHandler
from baserow.core.models import Agent, SubjectRollout
from baserow.core.subject.handler import SubjectHandler


@pytest.mark.django_db
def test_subject_fields_keep_storage_and_agent_attribution(data_fixture):
    """Subject consumers preserve physical storage and reject ineligible assignments."""
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_multiple_collaborators_field(table=table)
    author_field = data_fixture.create_created_by_field(table=table)
    modified_field = data_fixture.create_last_modified_by_field(table=table)
    agent = AgentHandler().create_agent(table.database.workspace, name="Assistant")
    SubjectRollout.objects.create(pk=1, agent_references_enabled=True)
    model = table.get_model()
    model_field = model._meta.get_field(field.db_column)
    through = model_field.remote_field.through
    assert through._meta.db_table == field.through_table_name
    assert (
        through._meta.get_fields()[2].column
        == f"multiplecollaboratorsfield{field.id}user_id"
    )
    with connection.cursor() as cursor:
        indexes_before = connection.introspection.get_constraints(
            cursor, field.through_table_name
        )
    row = RowHandler().force_create_row(
        agent, table, {field.db_column: [agent.subject_id, user.id]}
    )
    row.refresh_from_db()
    assert row.created_by_id == agent.subject_id
    assert getattr(row, author_field.db_column).id == agent.subject_id
    assert getattr(row, modified_field.db_column).id == agent.subject_id
    values = list(getattr(row, field.db_column).all())
    assert CollaboratorSerializer(values, many=True).data == [
        {"id": agent.subject_id, "name": "Assistant", "type": "core.Agent"},
        {"id": user.id, "name": user.first_name, "type": "auth.User"},
    ]
    agent.name = "Renamed"
    agent.save(update_fields=["name"])
    assert getattr(row, field.db_column).first().name == "Renamed"
    foreign = AgentHandler().create_agent(
        data_fixture.create_workspace(), name="Foreign"
    )
    field_type = field_type_registry.get("multiple_collaborators")
    with pytest.raises(ValidationError):
        field_type.prepare_value_for_db(field, [foreign.subject_id])
    agent.trashed = True
    agent.save(update_fields=["trashed"])
    with pytest.raises(ValidationError):
        field_type.prepare_value_for_db(field, [agent.subject_id])
    assert getattr(row, field.db_column).first().name == "Renamed"
    with connection.cursor() as cursor:
        assert (
            connection.introspection.get_constraints(cursor, field.through_table_name)
            == indexes_before
        )


@pytest.mark.django_db
def test_subject_options_query_count_is_bounded(
    data_fixture, django_assert_num_queries
):
    """Workspace Subject options remain one query after the identity migration."""
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    agent = AgentHandler().create_agent(workspace, name="Selectable Agent")
    with django_assert_num_queries(1):
        options = list(
            SubjectHandler().eligible_subjects(
                workspace.id, include_disabled_types=True
            )
        )
    assert {subject.id for subject in options} == {agent.subject_id, user.id}


@pytest.mark.django_db(transaction=True)
def test_agent_workspace_export_remaps_all_references_without_creating_actor(
    data_fixture,
):
    """All exported identity references share one safe destination mapping."""
    from io import BytesIO

    from baserow.core.handler import CoreHandler
    from baserow.core.models import Subject
    from baserow.core.registries import ImportExportConfig

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    workspace = table.database.workspace
    target = data_fixture.create_workspace(user=user)
    agent = AgentHandler().create_agent(workspace, name="Portable Agent")
    SubjectRollout.objects.create(pk=1, agent_references_enabled=True)
    field = data_fixture.create_multiple_collaborators_field(table=table)
    data_fixture.create_created_by_field(table=table)
    view = data_fixture.create_grid_view(table=table)
    from baserow.contrib.database.views.models import ViewDefaultValue

    ViewDefaultValue.objects.create(
        view=view,
        field=field,
        field_type="multiple_collaborators",
        enabled=True,
        value=[{"id": agent.subject_id}],
    )
    data_fixture.create_view_filter(
        view=view,
        field=field,
        type="multiple_collaborators_has",
        value=str(agent.subject_id),
    )
    RowHandler().force_create_row(agent, table, {field.db_column: [agent.subject_id]})
    handler = CoreHandler()
    config = ImportExportConfig(include_permission_data=False)
    exported = handler.export_workspace_applications(workspace, BytesIO(), config)
    manifest = exported[0]["tables"][0]["identity_manifest"]
    assert manifest["version"] == 1
    assert any(
        i["type"] == "core.Agent" and i["uid"] == str(agent.uid)
        for i in manifest["identities"].values()
    )
    agent_count = Agent.objects.count()
    imported, _ = handler.import_applications_to_workspace(
        target, exported, BytesIO(), config, None
    )
    imported_table = imported[0].table_set.get()
    imported_field = imported_table.field_set.get(name=field.name).specific
    row = imported_table.get_model().objects.get()
    collaborator = getattr(row, imported_field.db_column).get()
    assert collaborator.id != agent.subject_id
    assert collaborator.state == "retained"
    assert row.created_by_id == collaborator.id
    imported_default = ViewDefaultValue.objects.get(field=imported_field)
    assert imported_default.value == [
        {"id": collaborator.id, "name": "Portable Agent", "type": "core.Agent"}
    ]
    assert imported_table.view_set.get().viewfilter_set.get().value == str(
        collaborator.id
    )
    assert Subject.objects.get(pk=collaborator.id).uid == str(agent.uid)
    assert Agent.objects.count() == agent_count
    with pytest.raises(ValidationError):
        field_type_registry.get("multiple_collaborators").prepare_value_for_db(
            imported_field, [collaborator.id]
        )


@pytest.mark.django_db
def test_existing_history_metadata_stays_immutable_after_rename(data_fixture):
    """New identity caches never rewrite previously captured history metadata."""
    user = data_fixture.create_user(first_name="Original")
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_multiple_collaborators_field(table=table)
    row = RowHandler().force_create_row(user, table, {field.db_column: [user.id]})
    metadata = {"collaborators": {str(user.id): {"id": user.id, "name": "Historical"}}}
    user.first_name = "Renamed"
    user.save(update_fields=["first_name"])
    row = table.get_model().objects.all().enhance_by_fields().get(pk=row.id)
    serialized = field_type_registry.get(
        "multiple_collaborators"
    ).serialize_metadata_for_row_history(field, row, metadata)
    assert serialized["collaborators"] == {
        user.id: {"id": user.id, "name": "Historical"}
    }
    assert metadata == {
        "collaborators": {str(user.id): {"id": user.id, "name": "Historical"}}
    }


@pytest.mark.django_db
def test_collaborator_creation_does_not_activate_dormant_field_defaults(data_fixture):
    """Keep field-level defaults inactive and reject zero as an ordinary identity ID."""
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_multiple_collaborators_field(
        table=table, multiple_collaborators_default=[0, user.id]
    )
    handler = RowHandler()
    row = handler.force_create_row(user, table, {})
    assert list(getattr(row, field.db_column).all()) == []
    with pytest.raises(ValidationError):
        handler.force_create_row(user, table, {field.db_column: [0]})
