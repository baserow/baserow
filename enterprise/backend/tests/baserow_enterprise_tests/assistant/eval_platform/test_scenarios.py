import json

import pytest

from baserow_enterprise.assistant.evals.scenarios import (
    build_builder_ui_context,
    build_database_ui_context,
    build_workspace_ui_context,
    make_fixtures,
)


@pytest.mark.django_db
class TestMakeFixtures:
    def test_creates_user_outside_pytest_fixtures(self):
        fixtures = make_fixtures()

        user = fixtures.create_user()

        assert user.pk is not None
        assert user.email


@pytest.mark.django_db
class TestBuildDatabaseUiContext:
    def test_includes_workspace_and_database_ids(self):
        fixtures = make_fixtures()
        user = fixtures.create_user()
        database = fixtures.create_database_application(user=user)
        workspace = database.workspace

        ui_context = build_database_ui_context(user, workspace, database=database)
        data = json.loads(ui_context)

        assert data["workspace"]["id"] == workspace.id
        assert data["database"]["id"] == str(database.id)
        assert data["database"]["name"] == database.name
        assert data["user"]["id"] == user.id

    def test_includes_table_when_given(self):
        fixtures = make_fixtures()
        user = fixtures.create_user()
        table = fixtures.create_database_table(user=user)
        workspace = table.database.workspace

        ui_context = build_database_ui_context(
            user, workspace, database=table.database, table=table
        )
        data = json.loads(ui_context)

        assert data["table"]["id"] == table.id
        assert data["table"]["name"] == table.name

    def test_omits_database_and_table_when_not_given(self):
        fixtures = make_fixtures()
        user = fixtures.create_user()
        workspace = fixtures.create_workspace(user=user)

        ui_context = build_database_ui_context(user, workspace)
        data = json.loads(ui_context)

        assert "database" not in data
        assert "table" not in data


@pytest.mark.django_db
class TestBuildBuilderUiContext:
    def test_sets_application_slot_from_builder(self):
        fixtures = make_fixtures()
        user = fixtures.create_user()
        builder = fixtures.create_builder_application(user=user)
        workspace = builder.workspace

        ui_context = build_builder_ui_context(user, workspace, builder=builder)
        data = json.loads(ui_context)

        assert data["application"]["id"] == str(builder.id)
        assert data["application"]["name"] == builder.name
        assert "database" not in data

    def test_omits_application_when_not_given(self):
        fixtures = make_fixtures()
        user = fixtures.create_user()
        workspace = fixtures.create_workspace(user=user)

        ui_context = build_builder_ui_context(user, workspace)
        data = json.loads(ui_context)

        assert "application" not in data


@pytest.mark.django_db
class TestBuildWorkspaceUiContext:
    def test_has_only_workspace_and_user(self):
        fixtures = make_fixtures()
        user = fixtures.create_user()
        workspace = fixtures.create_workspace(user=user)

        ui_context = build_workspace_ui_context(user, workspace)
        data = json.loads(ui_context)

        assert data["workspace"]["id"] == workspace.id
        assert "database" not in data
        assert "application" not in data
        assert "table" not in data
