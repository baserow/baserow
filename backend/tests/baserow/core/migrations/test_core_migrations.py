from django.db import IntegrityError, connection, transaction
from django.utils import timezone

import pytest


@pytest.mark.once_per_day_in_ci
def test_0082_remove_duplicate_workspace_invitation_forwards(
    migrator, teardown_table_metadata
):
    migrate_from = [
        ("core", "0081_usersource_uid"),
    ]
    migrate_to = [
        (
            "core",
            "0083_alter_workspaceinvitation_unique_together",
        )
    ]

    old_state = migrator.migrate(migrate_from)
    User = old_state.apps.get_model("auth", "User")
    sender = User.objects.create(username="sender")
    Workspace = old_state.apps.get_model("core", "Workspace")
    Workspace.objects.bulk_create(
        [
            Workspace(id=1, name="wp1"),
            Workspace(id=2, name="wp2"),
        ]
    )

    WorkspaceInvitation = old_state.apps.get_model("core", "WorkspaceInvitation")

    WorkspaceInvitation.objects.bulk_create(
        [
            WorkspaceInvitation(
                id=1, email="a@baserow.io", workspace_id=1, invited_by_id=sender.id
            ),
            WorkspaceInvitation(
                id=2, email="a@baserow.io", workspace_id=1, invited_by_id=sender.id
            ),
            WorkspaceInvitation(
                id=3, email="a@baserow.io", workspace_id=2, invited_by_id=sender.id
            ),
            WorkspaceInvitation(
                id=4, email="b@baserow.io", workspace_id=1, invited_by_id=sender.id
            ),
            WorkspaceInvitation(
                id=5, email="b@baserow.io", workspace_id=2, invited_by_id=sender.id
            ),
            WorkspaceInvitation(
                id=6, email="b@baserow.io", workspace_id=2, invited_by_id=sender.id
            ),
            WorkspaceInvitation(
                id=7, email="c@baserow.io", workspace_id=2, invited_by_id=sender.id
            ),
            WorkspaceInvitation(
                id=8, email="c@baserow.io", workspace_id=2, invited_by_id=sender.id
            ),
            WorkspaceInvitation(
                id=9, email="c@baserow.io", workspace_id=2, invited_by_id=sender.id
            ),
            WorkspaceInvitation(
                id=10, email="c@baserow.io", workspace_id=2, invited_by_id=sender.id
            ),
        ]
    )

    assert WorkspaceInvitation.objects.count() == 10

    new_state = migrator.migrate(migrate_to)
    NewWorkspaceInvitation = new_state.apps.get_model("core", "WorkspaceInvitation")

    assert NewWorkspaceInvitation.objects.count() == 5
    remaining_ids = list(
        NewWorkspaceInvitation.objects.values_list("id", flat=True).order_by("id")
    )
    assert remaining_ids == [2, 3, 4, 6, 10]

    # And now it's not possible to create a new duplicate
    with pytest.raises(IntegrityError):
        NewWorkspaceInvitation.objects.create(
            email="a@baserow.io", workspace_id=1, invited_by_id=sender.id
        ),


@pytest.mark.once_per_day_in_ci
def test_0119_initializes_ai_provider_model_features_and_capabilities(
    migrator, teardown_table_metadata
):
    old_state = migrator.migrate(
        [("core", "0118_aiproviderworkspaceoverride_and_more")]
    )
    AIProviderConfig = old_state.apps.get_model("core", "AIProviderConfig")
    AIProviderModel = old_state.apps.get_model("core", "AIProviderModel")
    provider = AIProviderConfig.objects.create(
        provider_type="openai", api_key="test-key"
    )
    tested_model = AIProviderModel.objects.create(
        provider_config=provider,
        model_identifier="tested-model",
        last_test_at=timezone.now(),
        last_test_status="failure",
        last_test_error="provider unavailable",
    )
    untested_model = AIProviderModel.objects.create(
        provider_config=provider,
        model_identifier="untested-model",
    )

    new_state = migrator.migrate(
        [("core", "0119_aiproviderfeaturesetting_and_more")]
    )
    NewAIProviderModel = new_state.apps.get_model("core", "AIProviderModel")
    tested_model = NewAIProviderModel.objects.get(id=tested_model.id)
    untested_model = NewAIProviderModel.objects.get(id=untested_model.id)

    assert tested_model.feature_types == ["ai_fields"]
    assert tested_model.last_test_capabilities == {
        "text": {"status": "failure", "error": "provider unavailable"}
    }
    assert untested_model.feature_types == ["ai_fields"]
    assert untested_model.last_test_capabilities == {}


@pytest.mark.once_per_day_in_ci
def test_0120_makes_existing_ai_provider_models_available_to_ai_agents_and_reverses(
    migrator, teardown_table_metadata
):
    old_state = migrator.migrate(
        [("core", "0119_aiproviderfeaturesetting_and_more")]
    )
    AIProviderConfig = old_state.apps.get_model("core", "AIProviderConfig")
    AIProviderModel = old_state.apps.get_model("core", "AIProviderModel")
    provider = AIProviderConfig.objects.create(
        provider_type="openai", api_key="test-key"
    )
    historical_default_model = AIProviderModel.objects.create(
        provider_config=provider,
        model_identifier="historical-default-model",
        last_test_capabilities={
            "text": {"status": "success", "error": ""}
        },
    )
    assert historical_default_model.feature_types == ["ai_fields"]

    models = {
        feature_types[0] if feature_types else "none": AIProviderModel.objects.create(
            provider_config=provider,
            model_identifier=f"{index}-model",
            feature_types=feature_types,
            last_test_capabilities={
                "text": {"status": "success", "error": ""}
            },
        )
        for index, feature_types in enumerate(
            (
                ["ai_fields"],
                ["kuma"],
                [],
                ["ai_agent", "ai_fields"],
                ["extension_feature", "kuma"],
            )
        )
    }
    models["historical_default"] = historical_default_model

    new_state = migrator.migrate(
        [("core", "0120_add_ai_agent_provider_model_feature")]
    )
    NewAIProviderModel = new_state.apps.get_model("core", "AIProviderModel")

    expected_features = {
        "ai_fields": ["ai_fields", "ai_agent"],
        "kuma": ["kuma", "ai_agent"],
        "none": ["ai_agent"],
        "ai_agent": ["ai_agent", "ai_fields"],
        "extension_feature": ["extension_feature", "kuma", "ai_agent"],
        "historical_default": ["ai_fields", "ai_agent"],
    }
    for key, model in models.items():
        migrated_model = NewAIProviderModel.objects.get(id=model.id)
        assert migrated_model.feature_types == expected_features[key]
        assert migrated_model.last_test_capabilities == {
            "text": {"status": "success", "error": ""}
        }

    default_model = NewAIProviderModel.objects.create(
        provider_config_id=provider.id, model_identifier="new-orm-default"
    )
    assert default_model.feature_types == ["ai_fields", "ai_agent"]
    # Bypass the ORM's Python default to verify the actual database default.
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO core_aiprovidermodel (provider_config_id, model_identifier) "
            "VALUES (%s, %s) RETURNING id",
            [provider.id, "new-database-default"],
        )
        database_default_id = cursor.fetchone()[0]
    database_default_model = NewAIProviderModel.objects.get(id=database_default_id)
    assert database_default_model.feature_types == ["ai_fields", "ai_agent"]

    rolled_back_state = migrator.migrate(
        [("core", "0119_aiproviderfeaturesetting_and_more")]
    )
    RolledBackAIProviderModel = rolled_back_state.apps.get_model(
        "core", "AIProviderModel"
    )
    expected_rolled_back_features = {
        "ai_fields": ["ai_fields"],
        "kuma": ["kuma"],
        "none": [],
        "ai_agent": ["ai_fields"],
        "extension_feature": ["extension_feature", "kuma"],
        "historical_default": ["ai_fields"],
    }
    for key, model in models.items():
        rolled_back_model = RolledBackAIProviderModel.objects.get(id=model.id)
        assert rolled_back_model.feature_types == expected_rolled_back_features[key]
        assert rolled_back_model.last_test_capabilities == {
            "text": {"status": "success", "error": ""}
        }

    default_model = RolledBackAIProviderModel.objects.create(
        provider_config_id=provider.id, model_identifier="restored-orm-default"
    )
    assert default_model.feature_types == ["ai_fields"]
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO core_aiprovidermodel (provider_config_id, model_identifier) "
            "VALUES (%s, %s) RETURNING id",
            [provider.id, "restored-database-default"],
        )
        database_default_id = cursor.fetchone()[0]
    database_default_model = RolledBackAIProviderModel.objects.get(id=database_default_id)
    assert database_default_model.feature_types == ["ai_fields"]


@pytest.mark.once_per_day_in_ci
def test_0125_imports_legacy_ai_provider_settings(
    migrator, teardown_table_metadata, settings
):
    settings.BASEROW_OPENAI_API_KEY = "environment-key"
    settings.BASEROW_OPENAI_MODELS = ["gpt-5.4"]

    old_state = migrator.migrate([("core", "0121_agent")])
    Workspace = old_state.apps.get_model("core", "Workspace")
    malformed_workspaces = [
        Workspace.objects.create(
            name=f"malformed legacy settings {index}",
            generative_ai_models_settings=legacy_settings,
            trashed=trashed,
        )
        for index, (legacy_settings, trashed) in enumerate(
            (
                (["openai"], False),
                ("openai", False),
                ({"openai": {"api_key": "workspace-key", "models": 7}}, False),
                ({"openai": {"api_key": "workspace-key", "models": 1.5}}, False),
                ({"openai": {"api_key": "workspace-key", "models": True}}, False),
                (["openai"], True),
                ({"openai": {"api_key": "workspace-key", "models": True}}, True),
            )
        )
    ]
    workspace = Workspace.objects.create(
        name="with legacy settings",
        generative_ai_models_settings={
            "openai": {"api_key": "workspace-key", "models": ["gpt-5.4-mini"]}
        },
    )
    trashed_workspace = Workspace.objects.create(
        name="trashed with valid legacy settings",
        trashed=True,
        generative_ai_models_settings={
            "openai": {"api_key": "trashed-key", "models": ["trashed-model"]}
        },
    )
    without_settings = Workspace.objects.create(name="without legacy settings")
    original_settings = {
        candidate.id: candidate.generative_ai_models_settings
        for candidate in [
            *malformed_workspaces,
            workspace,
            trashed_workspace,
            without_settings,
        ]
    }

    new_state = migrator.migrate([("core", "0125_import_legacy_ai_provider_settings")])
    AIProviderConfig = new_state.apps.get_model("core", "AIProviderConfig")
    AIProviderModel = new_state.apps.get_model("core", "AIProviderModel")
    AIProviderWorkspaceOverride = new_state.apps.get_model(
        "core", "AIProviderWorkspaceOverride"
    )

    instance_provider = AIProviderConfig.objects.get(workspace__isnull=True)
    assert instance_provider.api_key == "environment-key"
    assert list(
        instance_provider.models.values_list("model_identifier", flat=True)
    ) == ["gpt-5.4"]
    assert instance_provider.models.get().feature_types == ["ai_fields", "ai_agent"]

    workspace_provider = AIProviderConfig.objects.get(workspace_id=workspace.id)
    assert workspace_provider.api_key == "workspace-key"
    assert workspace_provider.models.get().model_identifier == "gpt-5.4-mini"

    trashed_provider = AIProviderConfig.objects.get(workspace_id=trashed_workspace.id)
    assert trashed_provider.api_key == "trashed-key"
    assert trashed_provider.models.get().model_identifier == "trashed-model"
    assert AIProviderConfig.objects.count() == 3
    assert AIProviderModel.objects.count() == 3
    assert AIProviderWorkspaceOverride.objects.count() == 2
    assert not AIProviderConfig.objects.filter(
        workspace_id__in=[candidate.id for candidate in malformed_workspaces]
    ).exists()
    assert not AIProviderConfig.objects.filter(
        workspace_id=without_settings.id
    ).exists()
    assert (
        dict(
            Workspace.objects.filter(id__in=original_settings).values_list(
                "id", "generative_ai_models_settings"
            )
        )
        == original_settings
    )

    # The workspace defined its own connection, so it must not start inheriting the
    # instance models the import just created.
    assert set(
        AIProviderWorkspaceOverride.objects.values_list(
            "workspace_id", "provider_config_id"
        )
    ) == {
        (workspace.id, instance_provider.id),
        (trashed_workspace.id, instance_provider.id),
    }


@pytest.mark.once_per_day_in_ci
def test_0129_backfills_existing_templates_as_listed_official_templates(
    migrator, teardown_table_metadata
):
    old_state = migrator.migrate(
        [("core", "0127_mcpendpoint_allowed_tools")]
    )
    Template = old_state.apps.get_model("core", "Template")
    Workspace = old_state.apps.get_model("core", "Workspace")
    template = Template.objects.create(
        name="Template", slug="template", icon="file", workspace=Workspace.objects.create()
    )
    # Left behind when the sync failed to delete a template after its workspace.
    orphan = Template.objects.create(name="Orphan", slug="orphan", icon="file")

    new_state = migrator.migrate([("core", "0129_template_backfill_official")])
    NewTemplate = new_state.apps.get_model("core", "Template")

    migrated = NewTemplate.objects.get(id=template.id)
    assert migrated.type == "official"
    assert migrated.version == 1
    assert migrated.review_state == "approved"
    assert migrated.public_revision_id == template.id
    assert migrated.install_count == 0
    assert migrated.created_on is None
    assert migrated.updated_on is None

    # Without content it can't be listed.
    migrated_orphan = NewTemplate.objects.get(id=orphan.id)
    assert migrated_orphan.type == "official"
    assert migrated_orphan.review_state == "not_submitted"
    assert migrated_orphan.public_revision_id is None

    # The previous version keeps inserting templates during the deploy, without
    # knowing the new columns.
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO core_template "
            "(name, slug, icon, export_hash, keywords, open_application) "
            "VALUES ('Old', 'old', 'file', '', '', NULL) RETURNING id"
        )
        old_id = cursor.fetchone()[0]

    inserted = NewTemplate.objects.get(id=old_id)
    assert inserted.type is None
    assert inserted.version == 1
    assert inserted.review_state == "not_submitted"
    assert inserted.public_revision_id is None

    with pytest.raises(IntegrityError), transaction.atomic():
        NewTemplate.objects.create(name="Duplicate", slug="template", icon="file")

    NewTemplate.objects.update(public_revision=None)
    NewTemplate.objects.all().delete()


@pytest.mark.once_per_day_in_ci
def test_0128_upgrades_instance_with_duplicate_template_slugs(
    migrator, teardown_table_metadata
):
    # Two syncs running at the same time (the task before it was a singleton, or
    # `manage.py sync_templates` next to the task) each create a template for the
    # same file. Such an instance must still be able to upgrade, keeping both rows.
    old_state = migrator.migrate(
        [("core", "0127_mcpendpoint_allowed_tools")]
    )
    Template = old_state.apps.get_model("core", "Template")
    Workspace = old_state.apps.get_model("core", "Workspace")
    first = Template.objects.create(
        name="CRM", slug="crm", icon="file", workspace=Workspace.objects.create()
    )
    second = Template.objects.create(
        name="CRM", slug="crm", icon="file", workspace=Workspace.objects.create()
    )
    # Already uses the slug the duplicate would get with its id appended.
    taken = Template.objects.create(
        name="CRM", slug=f"crm-{second.id}", icon="file", workspace=Workspace.objects.create()
    )

    new_state = migrator.migrate([("core", "0129_template_backfill_official")])
    NewTemplate = new_state.apps.get_model("core", "Template")

    ids = [first.id, second.id, taken.id]
    rows = {t.id: t for t in NewTemplate.objects.filter(id__in=ids)}
    assert set(rows) == set(ids)
    assert rows[first.id].slug == "crm"
    assert rows[taken.id].slug == f"crm-{second.id}"
    assert rows[second.id].slug not in ("", "crm", f"crm-{second.id}")
    assert rows[second.id].workspace_id == second.workspace_id

    NewTemplate.objects.update(public_revision=None)
    NewTemplate.objects.all().delete()


@pytest.mark.once_per_day_in_ci
def test_0130_freezes_mcp_endpoints_without_an_allow_list(
    migrator, teardown_table_metadata
):
    old_state = migrator.migrate([("core", "0129_template_backfill_official")])
    User = old_state.apps.get_model("auth", "User")
    Workspace = old_state.apps.get_model("core", "Workspace")
    MCPEndpoint = old_state.apps.get_model("core", "MCPEndpoint")
    user = User.objects.create(username="mcp-freeze")
    workspace = Workspace.objects.create(name="ws")
    legacy = MCPEndpoint.objects.create(
        name="legacy", key="a" * 32, user=user, workspace=workspace
    )
    limited = MCPEndpoint.objects.create(
        name="limited",
        key="b" * 32,
        user=user,
        workspace=workspace,
        allowed_tools=["list_tables"],
    )

    new_state = migrator.migrate([("core", "0130_mcpendpoint_freeze_allowed_tools")])
    NewMCPEndpoint = new_state.apps.get_model("core", "MCPEndpoint")

    assert NewMCPEndpoint.objects.get(id=legacy.id).allowed_tools == [
        "list_databases",
        "list_tables",
        "get_table_schema",
        "list_table_rows",
        "create_rows",
        "update_rows",
        "delete_rows",
    ]
    assert NewMCPEndpoint.objects.get(id=limited.id).allowed_tools == ["list_tables"]

    NewMCPEndpoint.objects.all().delete()


@pytest.mark.once_per_day_in_ci
def test_0133_adds_template_metadata_and_lets_revisions_share_a_workspace(
    migrator, teardown_table_metadata
):
    def insert_template_like_the_previous_code(workspace_id, slug):
        # The previous code version doesn't know `metadata`.
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO core_template (name, slug, icon, keywords, workspace_id,
                    export_hash, type, version, review_state, reject_reason,
                    install_count, created_on, updated_on, description)
                VALUES ('T', %s, 'file', '', %s, '', 'official', 1, 'draft', '', 0,
                    now(), now(), '')
                RETURNING id
                """,
                [slug, workspace_id],
            )
            return cursor.fetchone()[0]

    old_state = migrator.migrate([("core", "0132_createusertemplatejob")])
    Workspace = old_state.apps.get_model("core", "Workspace")
    workspace = Workspace.objects.create(name="ws")
    existing_id = insert_template_like_the_previous_code(workspace.id, "existing")

    new_state = migrator.migrate([("core", "0133_template_shared_content")])
    NewTemplate = new_state.apps.get_model("core", "Template")

    # A row written by the previous code during the deploy shares the workspace.
    written_id = insert_template_like_the_previous_code(workspace.id, "written")
    assert NewTemplate.objects.get(id=existing_id).metadata == {}
    assert NewTemplate.objects.get(id=written_id).metadata == {}
    assert NewTemplate.objects.filter(workspace_id=workspace.id).count() == 2

    NewTemplate.objects.update(public_revision=None)
    NewTemplate.objects.all().delete()


@pytest.mark.once_per_day_in_ci
def test_0134_keeps_new_user_ids_above_legacy_agent_ids(
    migrator, teardown_table_metadata
):
    old_state = migrator.migrate([("core", "0133_template_shared_content")])
    Workspace = old_state.apps.get_model("core", "Workspace")
    OldAgent = old_state.apps.get_model("core", "Agent")
    OldUser = old_state.apps.get_model("auth", "User")
    workspace = Workspace.objects.create(name="ws")
    person = OldUser.objects.create(username="p@example.com", email="p@example.com")
    legacy = OldAgent.objects.create(
        id=person.id + 10, workspace=workspace, name="Legacy", trashed=True
    )
    new_state = migrator.migrate([("core", "0134_agent_user")])
    NewAgent = new_state.apps.get_model("core", "Agent")
    NewUser = new_state.apps.get_model("auth", "User")
    later = NewUser.objects.create(username="l@example.com", email="l@example.com")
    assert NewAgent._base_manager.get(id=legacy.id).user_id is None
    assert later.id > legacy.id

    reversed_state = migrator.migrate([("core", "0133_template_shared_content")])
    ReversedAgent = reversed_state.apps.get_model("core", "Agent")
    assert ReversedAgent._base_manager.get(id=legacy.id).name == "Legacy"
    assert "user" not in {field.name for field in ReversedAgent._meta.fields}
