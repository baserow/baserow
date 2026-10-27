from io import BytesIO

from django.urls import reverse

import pytest
from rest_framework import serializers
from rest_framework.status import HTTP_200_OK

from baserow.contrib.database.api.fields.serializers import FieldSerializer
from baserow.contrib.database.api.views.serializers import PublicFieldSerializer
from baserow.contrib.database.fields.actions import UpdateFieldActionType
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.registries import (
    FieldExtensionType,
    field_extension_registry,
    field_type_registry,
)
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig


class LabelField(serializers.Field):
    def __init__(self, extension, **kwargs):
        self.extension = extension
        super().__init__(source="*", read_only=True, **kwargs)

    def to_representation(self, field):
        return self.extension.labels.get(field.id)


class LabelFieldExtensionType(FieldExtensionType):
    type = "label"
    request_serializer_field_names = ["label"]
    serializer_field_names = ["label"]

    def __init__(self):
        super().__init__()
        self.labels = {}
        self.duplicated = []

    def get_request_serializer_field_overrides(self):
        return {"label": serializers.CharField(required=False)}

    def get_serializer_field_overrides(self):
        return {"label": LabelField(self)}

    def after_create(self, user, field, values):
        if "label" in values:
            self.labels[field.id] = values["label"]

    def after_update(self, user, field, old_field, values):
        if "label" in values:
            self.labels[field.id] = values["label"]

    def after_duplicate(self, user, original_field, new_field, duplicate_data):
        self.duplicated.append((original_field.id, new_field.id, duplicate_data))
        self.labels[new_field.id] = self.labels.get(original_field.id)

    def export_prepared_values(self, field):
        return {"label": self.labels.get(field.id)}

    # Exported with another name than the request property, which must not matter.
    def export_serialized(self, field, import_export_config):
        return {"text": self.labels.get(field.id)}

    def import_serialized(
        self, field, values, serialized_values, id_mapping, import_export_config
    ):
        self.labels[field.id] = values.get("text")


@pytest.fixture
def label_extension():
    before = field_extension_registry.registry.copy()
    extension = LabelFieldExtensionType()
    field_extension_registry.registry = {extension.type: extension}
    yield extension
    field_extension_registry.registry = before


@pytest.mark.django_db
def test_field_extension_values_via_api(api_client, data_fixture, label_extension):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Text", "type": "text", "label": "created"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    assert response.json()["label"] == "created"
    field_id = response.json()["id"]

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field_id}),
        {"label": "updated"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    assert response.json()["label"] == "updated"

    response = api_client.get(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert [field["label"] for field in response.json()] == ["updated"]


@pytest.mark.django_db
def test_field_extension_values_not_in_public_or_data_schema_serializers(
    data_fixture, label_extension
):
    field = data_fixture.create_text_field()
    field_type = field_type_registry.get_by_model(field)

    assert "label" not in field_type.get_serializer(field, PublicFieldSerializer).data
    assert (
        "label"
        not in field_type.get_serializer_class(
            base_class=PublicFieldSerializer
        )().fields
    )
    assert "label" in field_type.get_serializer(field, FieldSerializer).data
    assert (
        "label"
        not in field_type.get_serializer(
            field, FieldSerializer, extra_params={"data_schema": True}
        ).data
    )


@pytest.mark.django_db
def test_field_extension_values_undo_redo(data_fixture, label_extension):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    field = data_fixture.create_text_field(user=user)
    label_extension.labels[field.id] = "before"
    scopes = [UpdateFieldActionType.scope(field.table_id)]

    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user, field, label="after"
    )
    assert label_extension.labels[field.id] == "after"

    ActionHandler.undo(user, scopes, session_id)
    assert label_extension.labels[field.id] == "before"

    ActionHandler.redo(user, scopes, session_id)
    assert label_extension.labels[field.id] == "after"


@pytest.mark.django_db
def test_field_extension_values_duplicate_and_import_export(
    data_fixture, label_extension
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, name="Text")
    label_extension.labels[field.id] = "label"

    new_field, _ = FieldHandler().duplicate_field(user, field, duplicate_data=True)
    assert label_extension.duplicated == [(field.id, new_field.id, True)]
    assert label_extension.labels[new_field.id] == "label"

    config = ImportExportConfig(include_permission_data=False)
    database = table.database
    exported = database.get_type().export_serialized(
        database, config, files_zip=None, storage=None
    )
    workspace = data_fixture.create_workspace(user=user)
    imported = database.get_type().import_serialized(
        workspace, exported, config, {}, files_zip=None, storage=None
    )
    imported_field = imported.table_set.get().field_set.get(name="Text")
    assert label_extension.labels[imported_field.id] == "label"


@pytest.mark.django_db(transaction=True)
def test_field_extension_values_in_workspace_export(data_fixture, label_extension):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    label_extension.labels[field.id] = "label"

    exported = CoreHandler().export_workspace_applications(
        table.database.workspace,
        BytesIO(),
        ImportExportConfig(include_permission_data=False),
    )

    assert exported[0]["tables"][0]["fields"][0]["extensions"] == {
        "label": {"text": "label"}
    }


@pytest.mark.django_db
def test_field_extension_values_ignored_without_the_extension(
    data_fixture, label_extension
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, name="Text")
    label_extension.labels[field.id] = "label"
    config = ImportExportConfig(include_permission_data=False)
    database = table.database
    exported = database.get_type().export_serialized(
        database, config, files_zip=None, storage=None
    )

    # Like an instance on which the plugin of the extension isn't installed.
    field_extension_registry.registry = {}
    imported = database.get_type().import_serialized(
        data_fixture.create_workspace(user=user),
        exported,
        config,
        {},
        files_zip=None,
        storage=None,
    )

    assert imported.table_set.get().field_set.filter(name="Text").exists()
