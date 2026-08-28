from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from baserow.core.ai_provider.constants import (
    AI_PROVIDER_TYPES,
    PROVIDER_ENVIRONMENT_SETTINGS,
)
from baserow.core.ai_provider.exceptions import InvalidAIProviderSettings
from baserow.core.ai_provider.handler import AIProviderHandler
from baserow.core.ai_provider.models import AIProviderConfig
from baserow.core.ai_provider.provider_types import (
    get_environment_provider_values,
    get_legacy_workspace_provider_values,
    validate_provider_settings,
)
from baserow.core.models import Workspace

INSTANCE_SCOPE = "instance"
WORKSPACE_SCOPE = "workspace"
MIGRATION_SCOPES = (INSTANCE_SCOPE, WORKSPACE_SCOPE)


class Command(BaseCommand):
    help = (
        "Preview or apply an import of legacy AI settings at one scope "
        "into missing database-backed providers."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--scope",
            choices=MIGRATION_SCOPES,
            required=True,
            help=(
                "The scope to import: instance reads environment settings; "
                "workspace reads each workspace's legacy JSON settings."
            ),
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply the import atomically. Without this flag the command is read-only.",
        )

    def handle(self, *args, **options):
        scope = options["scope"]
        should_apply = options["apply"]
        if scope == INSTANCE_SCOPE:
            planned, skipped_count = self._plan_instance_import()
        else:
            planned, skipped_count = self._plan_workspace_import()

        if scope == INSTANCE_SCOPE and not planned and not skipped_count:
            self._report_unconfigured_instance_settings()
            if not should_apply:
                return

        if not should_apply:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Preview complete for the {scope} scope: {len(planned)} "
                    f"provider(s) to import, {skipped_count} left unchanged. No "
                    "changes were written; re-run with "
                    f"--scope {scope} --apply to import missing providers."
                )
            )
            return

        imported_count = 0
        with transaction.atomic():
            for values in planned:
                workspace = values["workspace"]
                if AIProviderConfig.objects.filter(
                    workspace=workspace,
                    provider_type=values["provider_type"],
                ).exists():
                    continue
                AIProviderHandler.create_provider(
                    workspace=workspace,
                    provider_type=values["provider_type"],
                    api_key=values["api_key"],
                    extra_settings=values["extra_settings"],
                    models_data=[
                        {"model_identifier": identifier}
                        for identifier in values["models"]
                    ],
                )
                imported_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {imported_count} missing {scope} provider(s)."
            )
        )

    def _plan_instance_import(self) -> tuple[list[dict[str, Any]], int]:
        existing_by_type = {
            provider.provider_type: provider
            for provider in AIProviderConfig.objects.filter(
                workspace__isnull=True
            ).prefetch_related("models")
        }
        planned = []
        skipped_count = 0
        for provider_type in PROVIDER_ENVIRONMENT_SETTINGS:
            values = get_environment_provider_values(provider_type)
            provider_name = AI_PROVIDER_TYPES[provider_type]["name"]
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
                self.stdout.write(
                    self.style.WARNING(
                        f"{provider_name}: skipping, its environment settings are "
                        f"incomplete ({exc})."
                    )
                )
                skipped_count += 1
                continue
            if provider_type in existing_by_type:
                skipped_count += 1
                differences = self._describe_existing_configuration(
                    existing_by_type[provider_type], values, "environment"
                )
                self.stdout.write(
                    self.style.WARNING(
                        f"{provider_name}: keeping existing database configuration "
                        f"({differences})."
                    )
                )
                continue
            planned.append({**values, "workspace": None})
            self.stdout.write(
                f"{provider_name}: import {len(values['models'])} model(s); "
                f"credential set: {'yes' if values['api_key'] else 'no'}."
            )
        return planned, skipped_count

    def _plan_workspace_import(self) -> tuple[list[dict[str, Any]], int]:
        existing = {
            (provider.workspace_id, provider.provider_type): provider
            for provider in AIProviderConfig.objects.filter(
                workspace__isnull=False
            ).prefetch_related("models")
        }
        planned = []
        skipped_count = 0

        for workspace in Workspace.objects.only(
            "id", "name", "generative_ai_models_settings"
        ).iterator():
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

                provider_name = AI_PROVIDER_TYPES[provider_type]["name"]
                prefix = f"Workspace {workspace.id} ({workspace.name}), {provider_name}"
                try:
                    values = get_legacy_workspace_provider_values(
                        provider_type, raw_values
                    )
                except InvalidAIProviderSettings as exc:
                    skipped_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"{prefix}: skipping incomplete legacy settings ({exc})."
                        )
                    )
                    continue

                existing_provider = existing.get((workspace.id, provider_type))
                if existing_provider is not None:
                    skipped_count += 1
                    differences = self._describe_existing_configuration(
                        existing_provider, values, "legacy settings"
                    )
                    self.stdout.write(
                        self.style.WARNING(
                            f"{prefix}: keeping existing database configuration "
                            f"({differences})."
                        )
                    )
                    continue

                planned.append({**values, "workspace": workspace})
                self.stdout.write(
                    f"{prefix}: import {len(values['models'])} model(s); credential "
                    f"set: {'yes' if values['api_key'] else 'no'}."
                )

        return planned, skipped_count

    @staticmethod
    def _describe_existing_configuration(
        provider: AIProviderConfig,
        incoming: dict[str, Any],
        incoming_label: str,
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
                f"settings only in {incoming_label}: "
                f"{', '.join(settings_only_in_incoming)}"
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

    def _report_unconfigured_instance_settings(self) -> None:
        self.stdout.write(
            self.style.WARNING(
                "No legacy AI provider environment settings are configured, so "
                "there is nothing to import."
            )
        )
        self.stdout.write("Checked the following environment variables:")
        for provider_type, config in PROVIDER_ENVIRONMENT_SETTINGS.items():
            variables = ", ".join(self._environment_variables(config))
            provider_name = AI_PROVIDER_TYPES[provider_type]["name"]
            self.stdout.write(f"  {provider_name}: {variables}")

    @staticmethod
    def _environment_variables(config: dict[str, Any]) -> list[str]:
        names = [config["api_key"]] if config["api_key"] else []
        names.append(config["models"])
        names.extend(config["extra_settings"].values())
        return names
