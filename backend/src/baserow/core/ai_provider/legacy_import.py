from dataclasses import dataclass
from typing import Any

from django.db.models import Q

from .constants import (
    AI_PROVIDER_FEATURE_AI_AGENT,
    AI_PROVIDER_FEATURE_AI_FIELDS,
    AI_PROVIDER_TYPES,
    PROVIDER_ENVIRONMENT_SETTINGS,
)
from .exceptions import InvalidAIProviderSettings
from .provider_types import (
    get_environment_provider_values,
    get_legacy_workspace_provider_values,
    validate_provider_settings,
)

SKIPPED_INCOMPLETE = "incomplete"
SKIPPED_EXISTING = "existing"

IMPORTED_MODEL_FEATURE_TYPES = [
    AI_PROVIDER_FEATURE_AI_FIELDS,
    AI_PROVIDER_FEATURE_AI_AGENT,
]


@dataclass(frozen=True, slots=True)
class PlannedProvider:
    """One provider the import would create, with its normalized settings."""

    provider_type: str
    api_key: str
    extra_settings: dict[str, Any]
    models: list[str]
    workspace_id: int | None = None
    workspace_name: str = ""


@dataclass(frozen=True, slots=True)
class SkippedProvider:
    """One legacy configuration the import leaves alone, and why."""

    provider_type: str
    kind: str
    reason: str
    workspace_id: int | None = None
    workspace_name: str = ""


@dataclass(frozen=True, slots=True)
class ImportPlan:
    planned: list[PlannedProvider]
    skipped: list[SkippedProvider]


def _manager(model: Any, using: str | None):
    return model.objects.using(using) if using else model.objects


def _exceeds_column_limits(
    values: dict[str, Any], provider_config_model: Any, provider_model_model: Any
) -> str | None:
    """
    Report why stored settings cannot fit the provider columns, if they cannot.

    Legacy settings were free-form JSON, so a value can be longer than the column
    that has to hold it. Importing one anyway raises DataError and aborts the whole
    upgrade, so an oversized entry is skipped like any other unusable one.

    :param values: The normalized provider values about to be imported.
    :param provider_config_model: The ``AIProviderConfig`` class that stores the credential.
    :param provider_model_model: The ``AIProviderModel`` class that stores identifiers.
    :returns: A reason string, or None when the values fit.
    """

    api_key_max = provider_config_model._meta.get_field("api_key").max_length
    identifier_max = provider_model_model._meta.get_field("model_identifier").max_length
    if api_key_max and len(values["api_key"]) > api_key_max:
        return f"its credential is longer than {api_key_max} characters"
    oversized = [
        identifier
        for identifier in values["models"]
        if identifier_max and len(identifier) > identifier_max
    ]
    if oversized:
        return (
            f"{len(oversized)} model identifier(s) are longer than "
            f"{identifier_max} characters"
        )
    return None


def plan_instance_import(
    provider_config_model: Any, provider_model_model: Any, using: str | None = None
) -> ImportPlan:
    """
    Plan the import of environment settings into missing instance providers.

    :param provider_config_model: The ``AIProviderConfig`` class to read, either the
        real model or a historical one supplied by a migration.
    :param provider_model_model: The ``AIProviderModel`` class, used to check that
        model identifiers fit their column.
    :param using: The database alias to read from, or None for the default.
    :returns: The providers to create and the configurations left unchanged.
    """

    existing_by_type = {
        provider.provider_type: provider
        for provider in _manager(provider_config_model, using)
        .filter(workspace__isnull=True)
        .prefetch_related("models")
    }
    planned: list[PlannedProvider] = []
    skipped: list[SkippedProvider] = []

    for provider_type in PROVIDER_ENVIRONMENT_SETTINGS:
        values = get_environment_provider_values(provider_type)
        if not values["configured"]:
            continue
        try:
            validate_provider_settings(
                provider_type,
                values["api_key"],
                values["extra_settings"],
                values["models"],
                require_credentials=True,
            )
        except InvalidAIProviderSettings as exc:
            skipped.append(
                SkippedProvider(
                    provider_type=provider_type,
                    kind=SKIPPED_INCOMPLETE,
                    reason=f"its environment settings are incomplete ({exc})",
                )
            )
            continue

        oversized = _exceeds_column_limits(
            values, provider_config_model, provider_model_model
        )
        if oversized is not None:
            skipped.append(
                SkippedProvider(
                    provider_type=provider_type,
                    kind=SKIPPED_INCOMPLETE,
                    reason=f"{oversized}",
                )
            )
            continue

        existing_provider = existing_by_type.get(provider_type)
        if existing_provider is not None:
            skipped.append(
                SkippedProvider(
                    provider_type=provider_type,
                    kind=SKIPPED_EXISTING,
                    reason=describe_existing_configuration(
                        existing_provider, values, "environment"
                    ),
                )
            )
            continue

        planned.append(
            PlannedProvider(
                provider_type=provider_type,
                api_key=values["api_key"],
                extra_settings=values["extra_settings"],
                models=values["models"],
            )
        )

    return ImportPlan(planned=planned, skipped=skipped)


def plan_workspace_import(
    provider_config_model: Any,
    provider_model_model: Any,
    workspace_model: Any,
    using: str | None = None,
) -> ImportPlan:
    """
    Plan the import of legacy workspace JSON into missing workspace providers.

    :param provider_config_model: The ``AIProviderConfig`` class to read.
    :param provider_model_model: The ``AIProviderModel`` class, used to check that
        model identifiers fit their column.
    :param workspace_model: The ``Workspace`` class to read.
    :param using: The database alias to read from, or None for the default.
    :returns: The providers to create and the configurations left unchanged.
    """

    existing = {
        (provider.workspace_id, provider.provider_type): provider
        for provider in _manager(provider_config_model, using)
        .filter(workspace__isnull=False)
        .prefetch_related("models")
    }
    planned: list[PlannedProvider] = []
    skipped: list[SkippedProvider] = []

    # Narrowing to rows that actually hold a supported provider key keeps this off a
    # full scan, and drops non-object settings the resolver cannot read either.
    workspaces = (
        _manager(workspace_model, using)
        .filter(
            generative_ai_models_settings__has_any_keys=list(
                PROVIDER_ENVIRONMENT_SETTINGS
            )
        )
        .only("id", "name", "generative_ai_models_settings")
    )

    for workspace in workspaces.iterator():
        legacy_settings = workspace.generative_ai_models_settings or {}
        for provider_type in PROVIDER_ENVIRONMENT_SETTINGS:
            if provider_type not in legacy_settings:
                continue
            raw_values = legacy_settings[provider_type]
            if isinstance(raw_values, dict):
                if not any(raw_values.values()):
                    continue
            elif not raw_values:
                continue

            try:
                values = get_legacy_workspace_provider_values(provider_type, raw_values)
            except InvalidAIProviderSettings as exc:
                skipped.append(
                    SkippedProvider(
                        provider_type=provider_type,
                        kind=SKIPPED_INCOMPLETE,
                        reason=f"incomplete legacy settings ({exc})",
                        workspace_id=workspace.id,
                        workspace_name=workspace.name,
                    )
                )
                continue

            oversized = _exceeds_column_limits(
                values, provider_config_model, provider_model_model
            )
            if oversized is not None:
                skipped.append(
                    SkippedProvider(
                        provider_type=provider_type,
                        kind=SKIPPED_INCOMPLETE,
                        reason=oversized,
                        workspace_id=workspace.id,
                        workspace_name=workspace.name,
                    )
                )
                continue

            existing_provider = existing.get((workspace.id, provider_type))
            if existing_provider is not None:
                skipped.append(
                    SkippedProvider(
                        provider_type=provider_type,
                        kind=SKIPPED_EXISTING,
                        reason=describe_existing_configuration(
                            existing_provider, values, "legacy settings"
                        ),
                        workspace_id=workspace.id,
                        workspace_name=workspace.name,
                    )
                )
                continue

            planned.append(
                PlannedProvider(
                    provider_type=provider_type,
                    api_key=values["api_key"],
                    extra_settings=values["extra_settings"],
                    models=values["models"],
                    workspace_id=workspace.id,
                    workspace_name=workspace.name,
                )
            )

    return ImportPlan(planned=planned, skipped=skipped)


def apply_import_plan(
    plan: ImportPlan,
    provider_config_model: Any,
    provider_model_model: Any,
    using: str | None = None,
) -> list[Any]:
    """
    Create the planned providers and their models, skipping any that now exist.

    The caller owns the transaction. Providers that appeared since the plan was built
    are left untouched, so applying the same plan twice imports nothing the second
    time.

    :param plan: The plan returned by one of the ``plan_*`` functions.
    :param provider_config_model: The ``AIProviderConfig`` class to write.
    :param provider_model_model: The ``AIProviderModel`` class to write.
    :param using: The database alias to write to, or None for the default.
    :returns: The providers created, for a caller that needs to act on them.
    """

    if not plan.planned:
        return []

    planned_workspace_ids = {provider.workspace_id for provider in plan.planned}
    scope = Q(workspace_id__in=[i for i in planned_workspace_ids if i is not None])
    if None in planned_workspace_ids:
        scope |= Q(workspace_id__isnull=True)
    existing = set(
        _manager(provider_config_model, using)
        .filter(scope)
        .values_list("workspace_id", "provider_type")
    )
    to_create = [
        provider
        for provider in plan.planned
        if (provider.workspace_id, provider.provider_type) not in existing
    ]
    if not to_create:
        return []

    created = _manager(provider_config_model, using).bulk_create(
        [
            provider_config_model(
                workspace_id=provider.workspace_id,
                provider_type=provider.provider_type,
                api_key=provider.api_key,
                extra_settings=provider.extra_settings,
            )
            for provider in to_create
        ]
    )
    _manager(provider_model_model, using).bulk_create(
        [
            provider_model_model(
                provider_config=config,
                model_identifier=identifier,
                is_enabled=True,
                feature_types=list(IMPORTED_MODEL_FEATURE_TYPES),
            )
            for config, provider in zip(created, to_create)
            for identifier in provider.models
        ]
    )
    return created


def suppress_inherited_instance_providers(
    workspace_providers: list[Any],
    provider_config_model: Any,
    workspace_override_model: Any,
    using: str | None = None,
) -> int:
    """
    Disable the same-type instance provider for each given workspace provider.

    Legacy workspace settings were authoritative on their own: a workspace that
    defined its own connection never saw the environment's models. Database providers
    compose differently, so without this a workspace that redefined a provider would
    start inheriting the instance models it never had.

    Call this after both scopes have been imported, so the instance providers this
    needs to point at already exist.

    :param workspace_providers: The imported workspace providers to opt out.
    :param provider_config_model: The ``AIProviderConfig`` class to read.
    :param workspace_override_model: The ``AIProviderWorkspaceOverride`` class to write.
    :param using: The database alias to use, or None for the default.
    :returns: The number of overrides created.
    """

    imported_workspace_providers = [
        provider
        for provider in workspace_providers
        if provider.workspace_id is not None
    ]
    if not imported_workspace_providers:
        return 0

    instance_provider_ids = dict(
        _manager(provider_config_model, using)
        .filter(
            workspace__isnull=True,
            provider_type__in={
                provider.provider_type for provider in imported_workspace_providers
            },
        )
        .values_list("provider_type", "id")
    )
    if not instance_provider_ids:
        return 0

    return len(
        _manager(workspace_override_model, using).bulk_create(
            [
                workspace_override_model(
                    workspace_id=provider.workspace_id,
                    provider_config_id=instance_provider_ids[provider.provider_type],
                )
                for provider in imported_workspace_providers
                if provider.provider_type in instance_provider_ids
            ],
            ignore_conflicts=True,
        )
    )


def describe_existing_configuration(
    provider: Any, incoming: dict[str, Any], incoming_label: str
) -> str:
    """Describe a skipped import without printing credential or setting values."""

    differences = []
    if provider.api_key != incoming["api_key"]:
        differences.append("credential differs")

    database_settings = provider.extra_settings or {}
    incoming_settings = incoming["extra_settings"] or {}
    settings_only_in_incoming = sorted(incoming_settings.keys() - database_settings)
    settings_only_in_database = sorted(database_settings.keys() - incoming_settings)
    changed_settings = sorted(
        key
        for key in incoming_settings.keys() & database_settings
        if incoming_settings[key] != database_settings[key]
    )
    if settings_only_in_incoming:
        differences.append(
            f"settings only in {incoming_label}: {', '.join(settings_only_in_incoming)}"
        )
    if settings_only_in_database:
        differences.append(
            f"settings only in database: {', '.join(settings_only_in_database)}"
        )
    if changed_settings:
        differences.append(
            f"settings with different values: {', '.join(changed_settings)}"
        )

    database_models = {model.model_identifier for model in provider.models.all()}
    incoming_models = set(incoming["models"])
    models_only_in_incoming = sorted(incoming_models - database_models)
    models_only_in_database = sorted(database_models - incoming_models)
    disabled_database_models = sorted(
        model.model_identifier
        for model in provider.models.all()
        if not model.is_enabled and model.model_identifier in incoming_models
    )
    if models_only_in_incoming:
        differences.append(
            f"models only in {incoming_label}: {', '.join(models_only_in_incoming)}"
        )
    if models_only_in_database:
        differences.append(
            f"models only in database: {', '.join(models_only_in_database)}"
        )
    if disabled_database_models:
        differences.append(
            f"models disabled in database: {', '.join(disabled_database_models)}"
        )
    if not provider.is_active:
        differences.append("database provider is disabled")

    return "; ".join(differences) or f"matches {incoming_label}"


def get_provider_name(provider_type: str) -> str:
    return AI_PROVIDER_TYPES[provider_type]["name"]
