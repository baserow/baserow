import pytest

from baserow.core.ai_provider.constants import (
    SCOPE_INSTANCE,
    SCOPE_WORKSPACE,
)
from baserow.core.ai_provider.exceptions import (
    AIProviderDoesNotExist,
    AIProviderModelDoesNotExist,
)
from baserow.core.ai_provider.handler import AIProviderHandler
from baserow.core.ai_provider.models import (
    AIProviderConfig,
)


@pytest.mark.django_db
def test_create_instance_provider(data_fixture):
    user = data_fixture.create_user(is_staff=True)
    provider = AIProviderHandler.create_provider(
        user=user,
        provider_type="openai",
        name="OpenAI Test",
        scope_type=SCOPE_INSTANCE,
        api_key="sk-test",
        extra_settings={"organization": "org-test"},
        models_data=[
            {
                "model_identifier": "gpt-4o",
                "features": ["ai_field", "ai_assistant"],
            },
            {
                "model_identifier": "gpt-4o-mini",
                "features": ["ai_field"],
            },
        ],
    )

    assert provider.provider_type == "openai"
    assert provider.name == "OpenAI Test"
    assert provider.api_key == "sk-test"
    assert provider.extra_settings == {"organization": "org-test"}
    assert provider.is_instance_level
    assert provider.is_active
    assert provider.created_by == user

    models = list(provider.models.all())
    assert len(models) == 2
    assert models[0].model_identifier == "gpt-4o"
    assert set(models[0].features.values_list("feature_type", flat=True)) == {
        "ai_field",
        "ai_assistant",
    }
    assert models[1].model_identifier == "gpt-4o-mini"
    assert set(models[1].features.values_list("feature_type", flat=True)) == {
        "ai_field",
    }


@pytest.mark.django_db
def test_create_workspace_provider(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    provider = AIProviderHandler.create_provider(
        user=user,
        provider_type="anthropic",
        name="Anthropic WS",
        scope_type=SCOPE_WORKSPACE,
        scope_id=workspace.id,
        api_key="sk-ant-test",
        models_data=[
            {"model_identifier": "claude-sonnet-4-20250514", "features": ["ai_field"]},
        ],
    )

    assert not provider.is_instance_level
    assert provider.scope_object_id == workspace.id


@pytest.mark.django_db
def test_get_provider(data_fixture):
    user = data_fixture.create_user(is_staff=True)
    provider = AIProviderHandler.create_provider(
        user=user,
        provider_type="openai",
        name="Test",
        scope_type=SCOPE_INSTANCE,
    )
    fetched = AIProviderHandler.get_provider(provider.id)
    assert fetched.id == provider.id
    assert fetched.name == "Test"


@pytest.mark.django_db
def test_get_provider_not_found():
    with pytest.raises(AIProviderDoesNotExist):
        AIProviderHandler.get_provider(99999)


@pytest.mark.django_db
def test_get_provider_model_not_found():
    with pytest.raises(AIProviderModelDoesNotExist):
        AIProviderHandler.get_provider_model(99999)


@pytest.mark.django_db
def test_update_provider(data_fixture):
    user = data_fixture.create_user(is_staff=True)
    provider = AIProviderHandler.create_provider(
        user=user,
        provider_type="openai",
        name="Old Name",
        scope_type=SCOPE_INSTANCE,
        api_key="old-key",
    )
    updated = AIProviderHandler.update_provider(
        user=user,
        provider=provider,
        name="New Name",
        api_key="new-key",
    )
    assert updated.name == "New Name"
    assert updated.api_key == "new-key"


@pytest.mark.django_db
def test_update_provider_with_models_data(data_fixture):
    user = data_fixture.create_user(is_staff=True)
    provider = AIProviderHandler.create_provider(
        user=user,
        provider_type="openai",
        name="Test",
        scope_type=SCOPE_INSTANCE,
        models_data=[
            {"model_identifier": "gpt-4o", "features": ["ai_field"]},
        ],
    )
    assert provider.models.count() == 1

    # Sync: adds gpt-4o-mini, updates gpt-4o features
    AIProviderHandler.update_provider(
        user=user,
        provider=provider,
        models_data=[
            {"model_identifier": "gpt-4o-mini", "features": ["ai_field"]},
            {"model_identifier": "gpt-4o", "features": ["ai_assistant"]},
        ],
    )
    models = {m.model_identifier: m for m in provider.models.all()}
    assert len(models) == 2
    assert "gpt-4o-mini" in models
    assert "gpt-4o" in models
    # gpt-4o was preserved (same ID), features updated
    assert set(models["gpt-4o"].features.values_list("feature_type", flat=True)) == {
        "ai_assistant"
    }
    assert set(
        models["gpt-4o-mini"].features.values_list("feature_type", flat=True)
    ) == {"ai_field"}


@pytest.mark.django_db
def test_delete_provider(data_fixture):
    user = data_fixture.create_user(is_staff=True)
    provider = AIProviderHandler.create_provider(
        user=user,
        provider_type="openai",
        name="Test",
        scope_type=SCOPE_INSTANCE,
    )
    provider_id = provider.id
    AIProviderHandler.delete_provider(user=user, provider=provider)
    assert not AIProviderConfig.objects.filter(id=provider_id).exists()


@pytest.mark.django_db
def test_list_providers_at_scope(data_fixture):
    user = data_fixture.create_user(is_staff=True)
    workspace = data_fixture.create_workspace(user=user)

    # Create instance-level
    AIProviderHandler.create_provider(
        user=user,
        provider_type="openai",
        name="Instance OpenAI",
        scope_type=SCOPE_INSTANCE,
    )
    # Create workspace-level
    AIProviderHandler.create_provider(
        user=user,
        provider_type="anthropic",
        name="WS Anthropic",
        scope_type=SCOPE_WORKSPACE,
        scope_id=workspace.id,
    )

    instance_providers = AIProviderHandler.list_providers(SCOPE_INSTANCE)
    assert len(instance_providers) == 1
    assert instance_providers[0].name == "Instance OpenAI"

    ws_providers = AIProviderHandler.list_providers(SCOPE_WORKSPACE, workspace.id)
    assert len(ws_providers) == 1
    assert ws_providers[0].name == "WS Anthropic"


@pytest.mark.django_db
def test_list_effective_providers(data_fixture):
    user = data_fixture.create_user(is_staff=True)
    workspace = data_fixture.create_workspace(user=user)

    # Instance-level provider
    AIProviderHandler.create_provider(
        user=user,
        provider_type="openai",
        name="Instance OpenAI",
        scope_type=SCOPE_INSTANCE,
    )
    # Workspace-level provider
    AIProviderHandler.create_provider(
        user=user,
        provider_type="anthropic",
        name="WS Anthropic",
        scope_type=SCOPE_WORKSPACE,
        scope_id=workspace.id,
    )

    effective = AIProviderHandler.list_effective_providers(
        SCOPE_WORKSPACE, workspace.id
    )
    assert len(effective) == 2

    # First one is inherited (instance), second is own (workspace)
    inherited = [e for e in effective if not e["is_own_scope"]]
    own = [e for e in effective if e["is_own_scope"]]
    assert len(inherited) == 1
    assert inherited[0]["provider"].name == "Instance OpenAI"
    assert inherited[0]["is_enabled"] is True
    assert len(own) == 1
    assert own[0]["provider"].name == "WS Anthropic"


@pytest.mark.django_db
def test_toggle_provider_override(data_fixture):
    user = data_fixture.create_user(is_staff=True)
    workspace = data_fixture.create_workspace(user=user)

    provider = AIProviderHandler.create_provider(
        user=user,
        provider_type="openai",
        name="Instance Provider",
        scope_type=SCOPE_INSTANCE,
        models_data=[
            {"model_identifier": "gpt-4o", "features": ["ai_field"]},
        ],
    )

    # Disable at workspace
    override = AIProviderHandler.toggle_provider_override(
        user=user,
        provider=provider,
        scope_type=SCOPE_WORKSPACE,
        scope_id=workspace.id,
        is_enabled=False,
    )
    assert override.is_enabled is False

    # Check effective list
    effective = AIProviderHandler.list_effective_providers(
        SCOPE_WORKSPACE, workspace.id
    )
    inherited = [e for e in effective if not e["is_own_scope"]]
    assert len(inherited) == 1
    assert inherited[0]["is_enabled"] is False

    # Re-enable
    override = AIProviderHandler.toggle_provider_override(
        user=user,
        provider=provider,
        scope_type=SCOPE_WORKSPACE,
        scope_id=workspace.id,
        is_enabled=True,
    )
    assert override.is_enabled is True


@pytest.mark.django_db
def test_get_available_models_for_feature(data_fixture):
    user = data_fixture.create_user(is_staff=True)
    workspace = data_fixture.create_workspace(user=user)

    AIProviderHandler.create_provider(
        user=user,
        provider_type="openai",
        name="Instance OpenAI",
        scope_type=SCOPE_INSTANCE,
        models_data=[
            {"model_identifier": "gpt-4o", "features": ["ai_field", "ai_assistant"]},
            {"model_identifier": "gpt-4o-mini", "features": ["ai_field"]},
        ],
    )

    # All ai_field models at instance
    models = AIProviderHandler.get_available_models_for_feature(
        "ai_field", SCOPE_INSTANCE
    )
    assert len(models) == 2
    assert {m.model_identifier for m in models} == {"gpt-4o", "gpt-4o-mini"}

    # ai_assistant models at instance
    models = AIProviderHandler.get_available_models_for_feature(
        "ai_assistant", SCOPE_INSTANCE
    )
    assert len(models) == 1
    assert models[0].model_identifier == "gpt-4o"

    # ai_field at workspace (inherits from instance)
    models = AIProviderHandler.get_available_models_for_feature(
        "ai_field", SCOPE_WORKSPACE, workspace.id
    )
    assert len(models) == 2


@pytest.mark.django_db
def test_available_models_excludes_disabled_provider(data_fixture):
    user = data_fixture.create_user(is_staff=True)
    workspace = data_fixture.create_workspace(user=user)

    provider = AIProviderHandler.create_provider(
        user=user,
        provider_type="openai",
        name="Instance OpenAI",
        scope_type=SCOPE_INSTANCE,
        models_data=[
            {"model_identifier": "gpt-4o", "features": ["ai_field"]},
        ],
    )

    # Disable at workspace
    AIProviderHandler.toggle_provider_override(
        user=user,
        provider=provider,
        scope_type=SCOPE_WORKSPACE,
        scope_id=workspace.id,
        is_enabled=False,
    )

    # Models should be empty at workspace
    models = AIProviderHandler.get_available_models_for_feature(
        "ai_field", SCOPE_WORKSPACE, workspace.id
    )
    assert len(models) == 0

    # But still available at instance
    models = AIProviderHandler.get_available_models_for_feature(
        "ai_field", SCOPE_INSTANCE
    )
    assert len(models) == 1


@pytest.mark.django_db
def test_feature_default_model(data_fixture):
    user = data_fixture.create_user(is_staff=True)
    workspace = data_fixture.create_workspace(user=user)

    provider = AIProviderHandler.create_provider(
        user=user,
        provider_type="openai",
        name="OpenAI",
        scope_type=SCOPE_INSTANCE,
        models_data=[
            {"model_identifier": "gpt-4o", "features": ["ai_assistant"]},
            {"model_identifier": "gpt-4o-mini", "features": ["ai_assistant"]},
        ],
    )
    gpt4o = provider.models.get(model_identifier="gpt-4o")
    gpt4o_mini = provider.models.get(model_identifier="gpt-4o-mini")

    # No default set
    default = AIProviderHandler.get_feature_default_model(
        "ai_assistant", SCOPE_INSTANCE
    )
    assert default is None

    # Set instance default
    AIProviderHandler.set_feature_default_model(
        user=user,
        feature_type="ai_assistant",
        provider_model=gpt4o,
        scope_type=SCOPE_INSTANCE,
    )
    default = AIProviderHandler.get_feature_default_model(
        "ai_assistant", SCOPE_INSTANCE
    )
    assert default.model_identifier == "gpt-4o"

    # Workspace inherits instance default
    default = AIProviderHandler.get_feature_default_model(
        "ai_assistant", SCOPE_WORKSPACE, workspace.id
    )
    assert default.model_identifier == "gpt-4o"

    # Override at workspace
    AIProviderHandler.set_feature_default_model(
        user=user,
        feature_type="ai_assistant",
        provider_model=gpt4o_mini,
        scope_type=SCOPE_WORKSPACE,
        scope_id=workspace.id,
    )
    default = AIProviderHandler.get_feature_default_model(
        "ai_assistant", SCOPE_WORKSPACE, workspace.id
    )
    assert default.model_identifier == "gpt-4o-mini"

    # Instance default unchanged
    default = AIProviderHandler.get_feature_default_model(
        "ai_assistant", SCOPE_INSTANCE
    )
    assert default.model_identifier == "gpt-4o"
