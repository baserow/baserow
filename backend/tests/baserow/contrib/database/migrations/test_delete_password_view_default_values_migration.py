import pytest


@pytest.mark.once_per_day_in_ci
def test_password_view_default_values_are_deleted(migrator, teardown_table_metadata):
    old_state = migrator.migrate(
        [("database", "0227_backfill_rowhistory_anonymous_actor_type")]
    )

    ContentType = old_state.apps.get_model("contenttypes", "ContentType")
    Workspace = old_state.apps.get_model("core", "Workspace")
    Database = old_state.apps.get_model("database", "Database")
    Table = old_state.apps.get_model("database", "Table")
    TextField = old_state.apps.get_model("database", "TextField")
    PasswordField = old_state.apps.get_model("database", "PasswordField")
    GridView = old_state.apps.get_model("database", "GridView")
    ViewDefaultValue = old_state.apps.get_model("database", "ViewDefaultValue")

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
    text_field = TextField.objects.create(
        table=table,
        name="text",
        order=1,
        primary=True,
        content_type=ContentType.objects.get_for_model(TextField),
    )
    converted_field = TextField.objects.create(
        table=table,
        name="converted",
        order=2,
        content_type=ContentType.objects.get_for_model(TextField),
    )
    password_field = PasswordField.objects.create(
        table=table,
        name="password",
        order=3,
        content_type=ContentType.objects.get_for_model(PasswordField),
    )
    view = GridView.objects.create(
        table=table,
        name="view",
        order=1,
        content_type=ContentType.objects.get_for_model(GridView),
    )
    kept = ViewDefaultValue.objects.create(
        view=view, field=text_field, value="keep me", field_type="text"
    )
    # Stored for a password field that was converted to text afterwards.
    ViewDefaultValue.objects.create(
        view=view, field=converted_field, value="secret", field_type="password"
    )
    # Stored for a text field that was converted to password afterwards.
    ViewDefaultValue.objects.create(
        view=view, field=password_field, value="secret", field_type="text"
    )

    new_state = migrator.migrate(
        [("database", "0228_delete_password_view_default_values")]
    )
    ViewDefaultValue = new_state.apps.get_model("database", "ViewDefaultValue")

    assert list(ViewDefaultValue.objects.values_list("id", flat=True)) == [kept.id]
