"""Read-only configuration inventory for an operator-led rollout rehearsal."""

from typing import Any

from django.apps import apps
from django.db.models import Q

from baserow.contrib.integrations.ai.models import AIAgentService, AIIntegration
from baserow.core.generative_ai.registries import generative_ai_model_type_registry
from baserow.core.models import Workspace

from .constants import PROVIDER_ENVIRONMENT_SETTINGS
from .models import (
    AIProviderConfig,
    AIProviderFeatureSetting,
    AIProviderWorkspaceOverride,
)
from .provider_types import get_environment_provider_values


def _describe_stored_settings(settings: Any) -> dict[str, Any]:
    """Describe the stored configuration without returning any setting values.

    :param settings: An untrusted legacy JSON value.
    :returns: Registered provider identifiers, a count of unrecognized keys, and
        whether the value is malformed. Untrusted keys are never echoed.
    """

    if not isinstance(settings, dict):
        return {"provider_types": [], "unknown_provider_count": 0, "malformed": True}
    registered = {
        provider.type for provider in generative_ai_model_type_registry.get_all()
    }
    configured = {key for key, value in settings.items() if value}
    return {
        "provider_types": sorted(configured & registered),
        "unknown_provider_count": len(configured - registered),
        "malformed": False,
    }


def _integration_context(integration: AIIntegration) -> dict[str, Any]:
    """Locate an integration's source workspace and published application.

    :param integration: An integration with its application relations loaded.
    :returns: Identifiers for the application, source workspace, and publication.
        A missing workspace remains None instead of guessing ownership.
    """

    application = integration.application
    workspace_id = application.workspace_id
    publication = None
    builder = getattr(application, "builder", None)
    automation = getattr(application, "automation", None)
    if builder is not None and (domain := getattr(builder, "published_from", None)):
        workspace_id = domain.builder.workspace_id
        publication = {"type": "builder", "domain_id": domain.id}
    elif automation is not None and automation.published_from_id is not None:
        workflow = automation.published_from
        workspace_id = workflow.automation.workspace_id
        publication = {
            "type": "automation",
            "source_workflow_id": workflow.id,
            "workflows": [
                {"id": published.id, "state": published.state}
                for published in automation.workflows.all()
            ],
        }
    return {
        "application_id": application.id,
        "application_trashed": application.trashed,
        "workspace_id": workspace_id,
        "publication": publication,
    }


def build_ai_provider_audit(workspace_id: int | None = None) -> dict[str, Any]:
    """Inventory stored AI configuration without modifying it or testing providers.

    The report deliberately omits credentials, connection values, prompts, user
    names, and saved test errors. It cannot infer the provenance of stored
    integration overrides or certify deployment or rollback safety. Trashed
    records are included and marked because restoration may reactivate them.

    :param workspace_id: Restrict consumers to this workspace, including its
        publications. None inventories every workspace and unbound AI services.
        Instance provider/default settings are included in either case.
    :returns: A JSON-serializable inventory with explicit manual verification needs.
    :raises Workspace.DoesNotExist: If the requested workspace does not exist.
    """

    workspaces = Workspace.objects_and_trash.order_by("id")
    scope = Q()
    if workspace_id is not None:
        workspaces = workspaces.filter(id=workspace_id)
        if not workspaces.exists():
            raise Workspace.DoesNotExist
        scope = Q(workspace_id=workspace_id) | Q(workspace_id__isnull=True)

    providers = AIProviderConfig.objects.filter(scope).order_by("id")
    providers = providers.prefetch_related("models")
    integrations = (
        AIIntegration.objects_and_trash.select_related(
            "application__builder__published_from__builder",
            "application__automation__published_from__automation",
        )
        .prefetch_related("application__automation__workflows")
        .order_by("id")
    )
    if workspace_id is not None:
        integrations = integrations.filter(
            Q(application__workspace_id=workspace_id)
            | Q(
                application__builder__published_from__builder__workspace_id=workspace_id
            )
            | Q(
                application__automation__published_from__automation__workspace_id=(
                    workspace_id
                )
            )
        )

    integration_rows = [
        {
            "id": integration.id,
            "trashed": integration.trashed,
            **_integration_context(integration),
            "override_settings": _describe_stored_settings(integration.ai_settings),
            "settings_provenance": "inherit"
            if integration.ai_settings == {}
            else "unknown",
        }
        for integration in integrations
    ]
    services = AIAgentService.objects_and_trash.order_by("id")
    if workspace_id is not None:
        services = services.filter(
            integration_id__in=[row["id"] for row in integration_rows]
        )

    try:
        ai_field_model = apps.get_model("baserow_premium", "AIField")
    except LookupError:
        ai_fields = None
    else:
        fields = ai_field_model.objects_and_trash.order_by("id")
        if workspace_id is not None:
            fields = fields.filter(table__database__workspace_id=workspace_id)
        ai_fields = list(
            fields.values(
                "id",
                "trashed",
                "table_id",
                "table__database__workspace_id",
                "ai_generative_ai_type",
                "ai_generative_ai_model",
            )
        )

    return {
        "format_version": 1,
        "workspace_id": workspace_id,
        "verification": "manual_rehearsal_required",
        "environment_provider_types": [
            provider_type
            for provider_type in PROVIDER_ENVIRONMENT_SETTINGS
            if get_environment_provider_values(provider_type)["configured"]
        ],
        "providers": [
            {
                "id": provider.id,
                "workspace_id": provider.workspace_id,
                "provider_type": provider.provider_type,
                "is_active": provider.is_active,
                "models": [
                    {
                        "id": model.id,
                        "identifier": model.model_identifier,
                        "is_enabled": model.is_enabled,
                        "feature_types": model.feature_types,
                    }
                    for model in sorted(
                        provider.models.all(), key=lambda model: model.id
                    )
                ],
            }
            for provider in providers
        ],
        "workspaces": [
            {
                "id": workspace.id,
                "trashed": workspace.trashed,
                "legacy_settings": _describe_stored_settings(
                    workspace.generative_ai_models_settings
                ),
            }
            for workspace in workspaces
        ],
        "disabled_instance_providers": list(
            AIProviderWorkspaceOverride.objects.filter(scope)
            .order_by("id")
            .values("workspace_id", "provider_config_id")
        ),
        "feature_settings": list(
            AIProviderFeatureSetting.objects.filter(scope)
            .order_by("id")
            .values("workspace_id", "feature_type", "model_id", "is_enabled")
        ),
        "ai_integrations": integration_rows,
        "ai_agents": list(
            services.values(
                "id",
                "trashed",
                "integration_id",
                "ai_generative_ai_type",
                "ai_generative_ai_model",
            )
        ),
        "ai_fields": ai_fields,
        "manual_checks": [
            "Reconcile both provider import previews under the final write pause.",
            "Verify Kuma's legacy model and native credential sources separately.",
            "Confirm the origin and intended account of every integration override.",
            "Check each published copy, including inactive Automation publications.",
            "Verify AI Fields, formula suggestions, Kuma, and both AI Agent surfaces "
            "with real providers, including credentials, endpoints, and eligibility.",
            "Rehearse process/browser cutover and rollback with the actual images "
            "and retained schema after credential changes.",
        ],
    }
