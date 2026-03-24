"""
Data migration: populate AIProviderConfig from legacy env vars and workspace
JSONField settings.

This migration is idempotent — it skips creation if matching records already exist.
"""

import os

from django.db import migrations


# Provider definitions: (provider_type, display_name, env_key_or_host,
#   env_models_key, extra_settings_env_keys)
PROVIDERS = [
    {
        "type": "openai",
        "name": "OpenAI",
        "api_key_env": "BASEROW_OPENAI_API_KEY",
        "models_env": "BASEROW_OPENAI_MODELS",
        "extra_env": {
            "organization": "BASEROW_OPENAI_ORGANIZATION",
            "base_url": "BASEROW_OPENAI_BASE_URL",
        },
    },
    {
        "type": "anthropic",
        "name": "Anthropic",
        "api_key_env": "BASEROW_ANTHROPIC_API_KEY",
        "models_env": "BASEROW_ANTHROPIC_MODELS",
        "extra_env": {},
    },
    {
        "type": "mistral",
        "name": "Mistral",
        "api_key_env": "BASEROW_MISTRAL_API_KEY",
        "models_env": "BASEROW_MISTRAL_MODELS",
        "extra_env": {},
    },
    {
        "type": "ollama",
        "name": "Ollama",
        "api_key_env": None,  # Ollama doesn't use an API key
        "host_env": "BASEROW_OLLAMA_HOST",
        "models_env": "BASEROW_OLLAMA_MODELS",
        "extra_env": {},
    },
    {
        "type": "openrouter",
        "name": "OpenRouter",
        "api_key_env": "BASEROW_OPENROUTER_API_KEY",
        "models_env": "BASEROW_OPENROUTER_MODELS",
        "extra_env": {
            "organization": "BASEROW_OPENROUTER_ORGANIZATION",
        },
    },
]


def _get_all_feature_types():
    """Return all known feature types for initial assignment."""
    return ["ai_field", "ai_assistant"]


def _create_models_for_config(AIProviderModel, AIProviderModelFeature, config, model_names):
    """Create AIProviderModel + feature records for a config."""
    features = _get_all_feature_types()
    for model_name in model_names:
        model_name = model_name.strip()
        if not model_name:
            continue
        provider_model = AIProviderModel.objects.create(
            provider_config=config,
            model_identifier=model_name,
            is_enabled=True,
        )
        for feature_type in features:
            AIProviderModelFeature.objects.create(
                provider_model=provider_model,
                feature_type=feature_type,
            )


def populate_from_env_vars(apps, schema_editor):
    """Create instance-level AIProviderConfig records from environment variables."""

    AIProviderConfig = apps.get_model("core", "AIProviderConfig")
    AIProviderModel = apps.get_model("core", "AIProviderModel")
    AIProviderModelFeature = apps.get_model("core", "AIProviderModelFeature")

    for provider_def in PROVIDERS:
        provider_type = provider_def["type"]

        # Check if this provider has any env var configured
        api_key = ""
        host = ""
        if provider_def.get("api_key_env"):
            api_key = os.getenv(provider_def["api_key_env"], "") or ""
        if provider_def.get("host_env"):
            host = os.getenv(provider_def["host_env"], "") or ""

        models_str = os.getenv(provider_def["models_env"], "") or ""
        model_names = [m.strip() for m in models_str.split(",") if m.strip()]

        # Skip if no credentials and no models
        is_ollama = provider_type == "ollama"
        has_credentials = bool(api_key) or (is_ollama and bool(host))
        if not has_credentials and not model_names:
            continue

        # Skip if already exists at instance scope
        existing = AIProviderConfig.objects.filter(
            provider_type=provider_type,
            scope_content_type__isnull=True,
            scope_object_id__isnull=True,
        ).exists()
        if existing:
            continue

        # Build extra_settings
        extra_settings = {}
        for key, env_name in provider_def.get("extra_env", {}).items():
            val = os.getenv(env_name, "") or ""
            if val:
                extra_settings[key] = val
        if host:
            extra_settings["host"] = host

        config = AIProviderConfig.objects.create(
            provider_type=provider_type,
            name=provider_def["name"],
            api_key=api_key,
            extra_settings=extra_settings,
            scope_content_type=None,
            scope_object_id=None,
            is_active=True,
        )

        _create_models_for_config(
            AIProviderModel, AIProviderModelFeature, config, model_names
        )


def populate_from_workspace_settings(apps, schema_editor):
    """
    Create workspace-level AIProviderConfig records from
    Workspace.generative_ai_models_settings JSONField.
    """

    Workspace = apps.get_model("core", "Workspace")
    ContentType = apps.get_model("contenttypes", "ContentType")
    AIProviderConfig = apps.get_model("core", "AIProviderConfig")
    AIProviderModel = apps.get_model("core", "AIProviderModel")
    AIProviderModelFeature = apps.get_model("core", "AIProviderModelFeature")

    workspace_ct = ContentType.objects.get_for_model(Workspace)

    for workspace in Workspace.objects.exclude(
        generative_ai_models_settings={}
    ).exclude(generative_ai_models_settings__isnull=True):
        settings = workspace.generative_ai_models_settings or {}

        for provider_type, provider_settings in settings.items():
            if not isinstance(provider_settings, dict):
                continue

            # Skip if already exists at this workspace scope
            existing = AIProviderConfig.objects.filter(
                provider_type=provider_type,
                scope_content_type=workspace_ct,
                scope_object_id=workspace.id,
            ).exists()
            if existing:
                continue

            api_key = provider_settings.get("api_key", "")
            model_names = provider_settings.get("models", [])

            # Build extra_settings from remaining keys
            extra_settings = {
                k: v
                for k, v in provider_settings.items()
                if k not in ("api_key", "models") and v
            }

            # Derive a name
            type_names = {
                "openai": "OpenAI",
                "anthropic": "Anthropic",
                "mistral": "Mistral",
                "ollama": "Ollama",
                "openrouter": "OpenRouter",
            }
            name = type_names.get(provider_type, provider_type.title())

            config = AIProviderConfig.objects.create(
                provider_type=provider_type,
                name=name,
                api_key=api_key or "",
                extra_settings=extra_settings,
                scope_content_type=workspace_ct,
                scope_object_id=workspace.id,
                is_active=True,
            )

            _create_models_for_config(
                AIProviderModel, AIProviderModelFeature, config, model_names
            )


def populate_from_ai_integrations(apps, schema_editor):
    """
    Create application-level AIProviderConfig records from
    AIIntegration.ai_settings JSONField (Builder AI integration).
    """

    try:
        AIIntegration = apps.get_model("integrations", "AIIntegration")
    except LookupError:
        return

    ContentType = apps.get_model("contenttypes", "ContentType")
    AIProviderConfig = apps.get_model("core", "AIProviderConfig")
    AIProviderModel = apps.get_model("core", "AIProviderModel")
    AIProviderModelFeature = apps.get_model("core", "AIProviderModelFeature")
    Application = apps.get_model("core", "Application")

    app_ct = ContentType.objects.get_for_model(Application)

    for integration in AIIntegration.objects.exclude(ai_settings={}).exclude(
        ai_settings__isnull=True
    ):
        settings = integration.ai_settings or {}
        app_id = integration.application_id

        for provider_type, provider_settings in settings.items():
            if not isinstance(provider_settings, dict):
                continue

            existing = AIProviderConfig.objects.filter(
                provider_type=provider_type,
                scope_content_type=app_ct,
                scope_object_id=app_id,
            ).exists()
            if existing:
                continue

            api_key = provider_settings.get("api_key", "")
            model_names = provider_settings.get("models", [])
            extra_settings = {
                k: v
                for k, v in provider_settings.items()
                if k not in ("api_key", "models") and v
            }

            type_names = {
                "openai": "OpenAI",
                "anthropic": "Anthropic",
                "mistral": "Mistral",
                "ollama": "Ollama",
                "openrouter": "OpenRouter",
            }
            name = type_names.get(provider_type, provider_type.title())

            config = AIProviderConfig.objects.create(
                provider_type=provider_type,
                name=name,
                api_key=api_key or "",
                extra_settings=extra_settings,
                scope_content_type=app_ct,
                scope_object_id=app_id,
                is_active=True,
            )

            _create_models_for_config(
                AIProviderModel, AIProviderModelFeature, config, model_names
            )


def backfill_ai_field_fk(apps, schema_editor):
    """
    Populate AIField.ai_provider_model FK from old string fields
    (ai_generative_ai_type + ai_generative_ai_model).
    """

    try:
        AIField = apps.get_model("baserow_premium", "AIField")
    except LookupError:
        return

    ContentType = apps.get_model("contenttypes", "ContentType")
    AIProviderModel = apps.get_model("core", "AIProviderModel")
    Workspace = apps.get_model("core", "Workspace")

    workspace_ct = ContentType.objects.get_for_model(Workspace)

    for field in AIField.objects.filter(
        ai_generative_ai_type__isnull=False,
        ai_generative_ai_model__isnull=False,
        ai_provider_model__isnull=True,
    ).select_related("table__database"):
        ai_type = field.ai_generative_ai_type
        ai_model = field.ai_generative_ai_model
        workspace_id = field.table.database.workspace_id

        # Search workspace-level configs first, then instance-level
        provider_model = _find_provider_model(
            AIProviderModel, ai_type, ai_model,
            workspace_ct, workspace_id,
        )
        if provider_model:
            AIField.objects.filter(pk=field.pk).update(
                ai_provider_model=provider_model
            )


def backfill_ai_agent_service_fk(apps, schema_editor):
    """
    Populate AIAgentService.ai_provider_model FK from old string fields.
    """

    try:
        AIAgentService = apps.get_model("integrations", "AIAgentService")
    except LookupError:
        return

    ContentType = apps.get_model("contenttypes", "ContentType")
    AIProviderModel = apps.get_model("core", "AIProviderModel")
    Application = apps.get_model("core", "Application")
    Workspace = apps.get_model("core", "Workspace")

    workspace_ct = ContentType.objects.get_for_model(Workspace)
    app_ct = ContentType.objects.get_for_model(Application)

    for service in AIAgentService.objects.filter(
        ai_generative_ai_type__isnull=False,
        ai_generative_ai_model__isnull=False,
        ai_provider_model__isnull=True,
    ).select_related("integration__application"):
        ai_type = service.ai_generative_ai_type
        ai_model = service.ai_generative_ai_model
        app_id = service.integration.application_id
        workspace_id = service.integration.application.workspace_id

        # Search application-level first, then workspace, then instance
        provider_model = (
            _find_provider_model(
                AIProviderModel, ai_type, ai_model,
                app_ct, app_id,
            )
            or _find_provider_model(
                AIProviderModel, ai_type, ai_model,
                workspace_ct, workspace_id,
            )
        )
        if provider_model:
            AIAgentService.objects.filter(pk=service.pk).update(
                ai_provider_model=provider_model
            )


def populate_assistant_default_model(apps, schema_editor):
    """
    Create AIFeatureDefaultModel for the AI assistant from
    BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL env var.
    """

    model_string = os.getenv("BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL", "")
    if not model_string:
        return

    AIProviderModel = apps.get_model("core", "AIProviderModel")
    AIFeatureDefaultModel = apps.get_model("core", "AIFeatureDefaultModel")

    # Parse "provider/model" or "provider:model" format
    # e.g. "groq:openai/gpt-oss-120b" or "openai/gpt-4o"
    slash_pos = model_string.find("/")
    colon_pos = model_string.find(":")
    if slash_pos != -1 and (colon_pos == -1 or slash_pos < colon_pos):
        model_id = model_string[slash_pos + 1:]
    elif colon_pos != -1:
        model_id = model_string[colon_pos + 1:]
    else:
        model_id = model_string

    # The model_id might still have a provider path (e.g. "openai/gpt-oss-120b")
    if "/" in model_id:
        model_id = model_id.rsplit("/", 1)[-1]

    # Find matching AIProviderModel at instance scope
    provider_model = AIProviderModel.objects.filter(
        provider_config__scope_content_type__isnull=True,
        provider_config__scope_object_id__isnull=True,
        model_identifier=model_id,
    ).first()

    if not provider_model:
        return

    # Check if default already exists
    existing = AIFeatureDefaultModel.objects.filter(
        feature_type="ai_assistant",
        scope_content_type__isnull=True,
        scope_object_id__isnull=True,
    ).exists()
    if existing:
        return

    AIFeatureDefaultModel.objects.create(
        feature_type="ai_assistant",
        provider_model=provider_model,
        scope_content_type=None,
        scope_object_id=None,
    )


def _find_provider_model(
    AIProviderModel, provider_type, model_identifier, scope_ct, scope_id,
):
    """
    Find an AIProviderModel matching the given type+model at the specified
    scope, then fall back to instance scope.
    """

    # Check at specified scope
    model = AIProviderModel.objects.filter(
        provider_config__provider_type=provider_type,
        provider_config__scope_content_type=scope_ct,
        provider_config__scope_object_id=scope_id,
        model_identifier=model_identifier,
    ).first()
    if model:
        return model

    # Fall back to instance scope
    return AIProviderModel.objects.filter(
        provider_config__provider_type=provider_type,
        provider_config__scope_content_type__isnull=True,
        provider_config__scope_object_id__isnull=True,
        model_identifier=model_identifier,
    ).first()


def forward(apps, schema_editor):
    populate_from_env_vars(apps, schema_editor)
    populate_from_workspace_settings(apps, schema_editor)
    populate_from_ai_integrations(apps, schema_editor)
    backfill_ai_field_fk(apps, schema_editor)
    backfill_ai_agent_service_fk(apps, schema_editor)
    populate_assistant_default_model(apps, schema_editor)


def reverse(apps, schema_editor):
    # Reversal: delete all AIProviderConfig records and clear FKs.
    # This is safe because the old systems (env vars, JSONField) still exist.
    AIProviderConfig = apps.get_model("core", "AIProviderConfig")
    AIProviderConfig.objects.all().delete()

    AIFeatureDefaultModel = apps.get_model("core", "AIFeatureDefaultModel")
    AIFeatureDefaultModel.objects.all().delete()

    try:
        AIField = apps.get_model("baserow_premium", "AIField")
        AIField.objects.filter(ai_provider_model__isnull=False).update(
            ai_provider_model=None
        )
    except LookupError:
        pass

    try:
        AIAgentService = apps.get_model("integrations", "AIAgentService")
        AIAgentService.objects.filter(ai_provider_model__isnull=False).update(
            ai_provider_model=None
        )
    except LookupError:
        pass


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0114_ai_provider"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    # Optional dependencies — these may not exist in all installations
    run_before = [
        ("baserow_premium", "0032_aifield_ai_provider_model"),
        ("integrations", "0028_aiagentservice_ai_provider_model"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
