from django.db import IntegrityError
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
