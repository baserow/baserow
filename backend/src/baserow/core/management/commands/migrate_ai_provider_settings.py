from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from baserow.core.ai_provider.constants import PROVIDER_ENVIRONMENT_SETTINGS
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
        existing_types = set(
            AIProviderConfig.objects.filter(workspace__isnull=True).values_list(
                "provider_type", flat=True
            )
        )
        planned = []
        skipped_count = 0
        for provider_type in PROVIDER_ENVIRONMENT_SETTINGS:
            values = get_environment_provider_values(provider_type)
            provider_name = PROVIDER_ENVIRONMENT_SETTINGS[provider_type]["name"]
            if not values["configured"]:
                continue
            if provider_type in existing_types:
                skipped_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"{provider_name}: keeping existing database configuration."
                    )
                )
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
            planned.append({**values, "workspace": None})
            self.stdout.write(
                f"{provider_name}: import {len(values['models'])} model(s); "
                f"credential set: {'yes' if values['api_key'] else 'no'}."
            )
        return planned, skipped_count

    def _plan_workspace_import(self) -> tuple[list[dict[str, Any]], int]:
        existing = set(
            AIProviderConfig.objects.filter(workspace__isnull=False).values_list(
                "workspace_id", "provider_type"
            )
        )
        planned = []
        skipped_count = 0

        for workspace in Workspace.objects.only(
            "id", "name", "generative_ai_models_settings"
        ).iterator():
            legacy_settings = workspace.generative_ai_models_settings or {}
            for provider_type, config in PROVIDER_ENVIRONMENT_SETTINGS.items():
                if provider_type not in legacy_settings:
                    continue
                raw_values = legacy_settings[provider_type]
                if isinstance(raw_values, dict):
                    if not any(raw_values.values()):
                        continue
                elif not raw_values:
                    continue

                provider_name = config["name"]
                prefix = f"Workspace {workspace.id} ({workspace.name}), {provider_name}"
                if (workspace.id, provider_type) in existing:
                    skipped_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"{prefix}: keeping existing database configuration."
                        )
                    )
                    continue

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

                planned.append({**values, "workspace": workspace})
                self.stdout.write(
                    f"{prefix}: import {len(values['models'])} model(s); credential "
                    f"set: {'yes' if values['api_key'] else 'no'}."
                )

        return planned, skipped_count

    def _report_unconfigured_instance_settings(self) -> None:
        self.stdout.write(
            self.style.WARNING(
                "No legacy AI provider environment settings are configured, so "
                "there is nothing to import."
            )
        )
        self.stdout.write("Checked the following environment variables:")
        for config in PROVIDER_ENVIRONMENT_SETTINGS.values():
            variables = ", ".join(self._environment_variables(config))
            self.stdout.write(f"  {config['name']}: {variables}")

    @staticmethod
    def _environment_variables(config: dict[str, Any]) -> list[str]:
        names = [config["api_key"]] if config["api_key"] else []
        names.append(config["models"])
        names.extend(config["extra_settings"].values())
        return names
