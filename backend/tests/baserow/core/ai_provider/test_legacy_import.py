import pytest

from baserow.core.ai_provider.constants import (
    AI_PROVIDER_FEATURE_AI_AGENT,
    AI_PROVIDER_FEATURE_AI_FIELDS,
    AI_PROVIDER_FEATURE_KUMA,
    AI_PROVIDER_FEATURE_MODE_INHERIT,
    AI_PROVIDER_FEATURE_MODE_MODEL,
)
from baserow.core.ai_provider.handler import AIProviderHandler
from baserow.core.ai_provider.legacy_import import (
    apply_import_plan,
    plan_instance_import,
    plan_workspace_import,
    suppress_inherited_instance_providers,
)
from baserow.core.ai_provider.models import (
    AIProviderConfig,
    AIProviderModel,
    AIProviderWorkspaceOverride,
)
from baserow.core.ai_provider.registries import ai_provider_model_feature_type_registry
from baserow.core.ai_provider.resolution import clear_ai_provider_state_cache
from baserow.core.generative_ai.registries import generative_ai_model_type_registry
from baserow.core.models import Workspace

FEATURE_TYPES = [AI_PROVIDER_FEATURE_AI_FIELDS, AI_PROVIDER_FEATURE_AI_AGENT]

LEGACY_SHAPES = [
    {"api_key": "key", "models": ["gpt-5.4"]},
    {"api_key": "key", "models": "gpt-5.4,gpt-5.4-mini"},
    {"api_key": "key", "models": ["gpt-5.4"], "organization": "org-1"},
    {"api_key": "key", "models": []},
    {"api_key": "key"},
    {"models": ["gpt-5.4"]},
    {"api_key": "   ", "models": ["gpt-5.4"]},
    {"api_key": "", "models": []},
    {"api_key": "key", "models": ["gpt-5.4"], "unsupported_key": "value"},
    [],
    "nonsense",
]


def _import_everything():
    apply_import_plan(
        plan_instance_import(AIProviderConfig, AIProviderModel),
        AIProviderConfig,
        AIProviderModel,
    )
    imported_workspace_providers = apply_import_plan(
        plan_workspace_import(AIProviderConfig, AIProviderModel, Workspace),
        AIProviderConfig,
        AIProviderModel,
    )
    suppress_inherited_instance_providers(
        imported_workspace_providers, AIProviderConfig, AIProviderWorkspaceOverride
    )
    clear_ai_provider_state_cache()


@pytest.mark.django_db
@pytest.mark.parametrize("legacy_values", LEGACY_SHAPES)
def test_import_covers_exactly_what_the_resolver_reads(data_fixture, legacy_values):
    """
    Complete legacy settings that fit the database columns should be imported.
    """

    workspace = data_fixture.create_workspace(
        generative_ai_models_settings={"openai": legacy_values}
    )
    model_type = generative_ai_model_type_registry.get("openai")

    resolver_reads_legacy = (
        model_type._get_complete_legacy_workspace_settings(workspace) is not None
    )
    plan = plan_workspace_import(AIProviderConfig, AIProviderModel, Workspace)
    import_plans_it = any(
        planned.workspace_id == workspace.id and planned.provider_type == "openai"
        for planned in plan.planned
    )

    assert import_plans_it == resolver_reads_legacy


@pytest.mark.django_db
def test_availability_is_unchanged_by_the_import(data_fixture, settings):
    settings.BASEROW_OPENAI_API_KEY = "environment-key"
    settings.BASEROW_OPENAI_MODELS = ["gpt-5.4", "gpt-5.4-mini"]
    settings.BASEROW_OPENAI_ORGANIZATION = "environment-org"

    with_legacy = data_fixture.create_workspace(
        generative_ai_models_settings={
            "openai": {"api_key": "workspace-key", "models": ["gpt-5.4-mini"]}
        }
    )
    without_legacy = data_fixture.create_workspace()
    model_type = generative_ai_model_type_registry.get("openai")

    def availability():
        clear_ai_provider_state_cache()
        return {
            (workspace.id, feature_type): model_type.get_enabled_models_for_feature(
                feature_type, workspace=workspace
            )
            for workspace in (with_legacy, without_legacy)
            for feature_type in FEATURE_TYPES
        }

    before = availability()
    _import_everything()
    after = availability()

    assert after == before
    assert before[(with_legacy.id, AI_PROVIDER_FEATURE_AI_FIELDS)] == ["gpt-5.4-mini"]
    assert before[(without_legacy.id, AI_PROVIDER_FEATURE_AI_FIELDS)] == [
        "gpt-5.4",
        "gpt-5.4-mini",
    ]


@pytest.mark.django_db
def test_import_leaves_kuma_without_eligible_models(data_fixture, settings):
    """Kuma eligibility is an explicit choice, so imported models never carry it."""

    settings.BASEROW_OPENAI_API_KEY = "environment-key"
    settings.BASEROW_OPENAI_MODELS = ["gpt-5.4"]
    workspace = data_fixture.create_workspace()
    model_type = generative_ai_model_type_registry.get("openai")

    _import_everything()

    assert (
        model_type.get_enabled_models_for_feature(
            AI_PROVIDER_FEATURE_KUMA, workspace=workspace
        )
        == []
    )


@pytest.mark.django_db
def test_imported_workspace_keeps_inheriting_the_instance_kuma_model(
    data_fixture, settings
):
    settings.BASEROW_OPENAI_API_KEY = "environment-key"
    settings.BASEROW_OPENAI_MODELS = ["gpt-5.4"]
    settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL = ""
    workspace = data_fixture.create_workspace(
        generative_ai_models_settings={
            "openai": {"api_key": "workspace-key", "models": ["gpt-5.4-mini"]}
        }
    )
    model_type = generative_ai_model_type_registry.get("openai")

    _import_everything()
    instance_provider = AIProviderConfig.objects.get(workspace__isnull=True)
    instance_model = instance_provider.models.get()
    AIProviderHandler.update_model(
        instance_model, feature_types=[*FEATURE_TYPES, AI_PROVIDER_FEATURE_KUMA]
    )
    AIProviderHandler.update_feature_setting(
        AI_PROVIDER_FEATURE_KUMA, AI_PROVIDER_FEATURE_MODE_MODEL, model=instance_model
    )

    assert AIProviderWorkspaceOverride.objects.filter(
        workspace=workspace, provider_config=instance_provider
    ).exists()
    kuma = AIProviderHandler.list_feature_settings(workspace)[0]
    assert kuma["mode"] == AI_PROVIDER_FEATURE_MODE_INHERIT
    assert kuma["state"] == "inherited"
    assert kuma["model"] == instance_model
    assert kuma["inherited_state"] == "configured"
    availability = ai_provider_model_feature_type_registry.get_workspace_availability(
        workspace
    )
    assert availability[AI_PROVIDER_FEATURE_KUMA] == {
        "is_enabled": True,
        "state": "inherited",
    }
    assert availability[AI_PROVIDER_FEATURE_AI_FIELDS]["models"] == {
        "openai": ["gpt-5.4-mini"]
    }
    for feature_type in FEATURE_TYPES:
        assert model_type.get_enabled_models_for_feature(
            feature_type, workspace=workspace
        ) == ["gpt-5.4-mini"]


@pytest.mark.django_db
def test_import_is_idempotent_and_preserves_existing_providers(data_fixture, settings):
    settings.BASEROW_OPENAI_API_KEY = "environment-key"
    settings.BASEROW_OPENAI_MODELS = ["gpt-5.4"]
    workspace = data_fixture.create_workspace(
        generative_ai_models_settings={
            "openai": {"api_key": "workspace-key", "models": ["gpt-5.4-mini"]}
        }
    )

    _import_everything()
    _import_everything()

    assert AIProviderConfig.objects.count() == 2
    instance_provider = AIProviderConfig.objects.get(workspace__isnull=True)
    assert instance_provider.api_key == "environment-key"
    workspace_provider = AIProviderConfig.objects.get(workspace=workspace)
    assert workspace_provider.api_key == "workspace-key"
    assert list(
        workspace_provider.models.values_list("model_identifier", "feature_types")
    ) == [
        ("gpt-5.4-mini", [AI_PROVIDER_FEATURE_AI_FIELDS, AI_PROVIDER_FEATURE_AI_AGENT])
    ]
    workspace.refresh_from_db()
    assert workspace.generative_ai_models_settings["openai"]["api_key"] == (
        "workspace-key"
    )


# Shapes observed in production: a credential without models, and models without a
# credential. Both resolve differently than they did before the flag was removed; the
# import must at least not move them again.
PARTIAL_LEGACY_SHAPES = [
    {"api_key": "workspace-key", "models": []},
    {"models": ["gpt-4"]},
]


@pytest.mark.django_db
@pytest.mark.parametrize("legacy_values", PARTIAL_LEGACY_SHAPES)
def test_partial_legacy_settings_survive_the_import(
    data_fixture, settings, legacy_values
):
    settings.BASEROW_OPENAI_API_KEY = "environment-key"
    settings.BASEROW_OPENAI_MODELS = ["gpt-5.4", "gpt-5.4-mini"]
    workspace = data_fixture.create_workspace(
        generative_ai_models_settings={"openai": legacy_values}
    )
    model_type = generative_ai_model_type_registry.get("openai")

    def availability():
        clear_ai_provider_state_cache()
        return model_type.get_enabled_models_for_feature(
            AI_PROVIDER_FEATURE_AI_FIELDS, workspace=workspace
        )

    before = availability()
    _import_everything()

    assert availability() == before


@pytest.mark.django_db
@pytest.mark.parametrize(
    "legacy_values",
    [
        {
            "api_key": "k" * 600,
            "models": ["gpt-4o"],
            "base_url": "https://workspace.example/v1",
        },
        {"api_key": "k", "models": ["m" * 400]},
    ],
)
def test_oversized_legacy_settings_keep_working_after_import(
    data_fixture, settings, legacy_values
):
    """Skipped workspace settings keep their own models and connection."""

    settings.BASEROW_OPENAI_API_KEY = "environment-key"
    settings.BASEROW_OPENAI_MODELS = ["environment-model"]
    workspace = data_fixture.create_workspace(
        generative_ai_models_settings={"openai": legacy_values}
    )
    model_type = generative_ai_model_type_registry.get("openai")

    def availability():
        return {
            feature: model_type.get_enabled_models_for_feature(
                feature, workspace=workspace
            )
            for feature in FEATURE_TYPES
        }

    before = availability()
    assert before == {feature: legacy_values["models"] for feature in FEATURE_TYPES}
    expected_connection = {"base_url": None, "organization": None, **legacy_values}
    model_name = legacy_values["models"][0]
    assert (
        model_type.get_model_settings_override(model_name, workspace)
        == expected_connection
    )

    plan = plan_workspace_import(AIProviderConfig, AIProviderModel, Workspace)
    assert plan.planned == []
    assert [s.workspace_id for s in plan.skipped] == [workspace.id]
    assert "longer than" in plan.skipped[0].reason

    _import_everything()

    assert not AIProviderConfig.objects.filter(workspace=workspace).exists()
    assert AIProviderConfig.objects.get(workspace__isnull=True).api_key == (
        "environment-key"
    )
    assert availability() == before
    assert model_type.get_api_key(workspace) == legacy_values["api_key"]
    assert (
        model_type.get_model_settings_override(model_name, workspace)
        == expected_connection
    )


@pytest.mark.django_db
@pytest.mark.parametrize("scope", ["instance", "workspace"])
def test_malformed_ollama_host_does_not_abort_import(data_fixture, settings, scope):
    settings.BASEROW_OPENAI_API_KEY = "environment-key"
    settings.BASEROW_OPENAI_MODELS = ["gpt-5.4"]
    legacy_settings = {
        "openai": {"api_key": "workspace-key", "models": ["gpt-5.4-mini"]}
    }
    if scope == "instance":
        settings.BASEROW_OLLAMA_HOST = "http://["
        settings.BASEROW_OLLAMA_MODELS = ["llama3"]
    else:
        legacy_settings["ollama"] = {"host": "http://[", "models": ["llama3"]}
    workspace = data_fixture.create_workspace(
        generative_ai_models_settings=legacy_settings
    )

    if scope == "instance":
        plan = plan_instance_import(AIProviderConfig, AIProviderModel)
    else:
        plan = plan_workspace_import(AIProviderConfig, AIProviderModel, Workspace)
    assert len(plan.skipped) == 1
    assert plan.skipped[0].provider_type == "ollama"
    assert "valid URL" in plan.skipped[0].reason

    _import_everything()

    assert AIProviderConfig.objects.count() == 2
    instance_provider = AIProviderConfig.objects.get(workspace__isnull=True)
    assert instance_provider.api_key == "environment-key"
    assert instance_provider.models.get().model_identifier == "gpt-5.4"
    workspace_provider = AIProviderConfig.objects.get(workspace=workspace)
    assert workspace_provider.api_key == "workspace-key"
    assert workspace_provider.models.get().model_identifier == "gpt-5.4-mini"
    assert not AIProviderConfig.objects.filter(provider_type="ollama").exists()
