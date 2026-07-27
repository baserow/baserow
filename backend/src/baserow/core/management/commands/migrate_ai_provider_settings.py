from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from baserow.core.ai_provider.constants import PROVIDER_ENVIRONMENT_SETTINGS
from baserow.core.ai_provider.exceptions import InvalidAIProviderSettings
from baserow.core.ai_provider.handler import AIProviderHandler
from baserow.core.ai_provider.models import AIProviderConfig
from baserow.core.ai_provider.provider_types import (
    get_environment_provider_values,
    validate_provider_settings,
)


class Command(BaseCommand):
    help = (
        "Preview or apply an import of legacy instance AI environment settings "
        "into missing database-backed providers."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply the import atomically. Without this flag the command is read-only.",
        )

    def handle(self, *args, **options):
        should_apply = options["apply"]
        existing_types = set(
            AIProviderConfig.objects.values_list("provider_type", flat=True)
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
                continue
            planned.append(values)
            self.stdout.write(
                f"{provider_name}: import {len(values['models'])} model(s); "
                f"credential set: {'yes' if values['api_key'] else 'no'}."
            )

        if not planned and not skipped_count:
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
            if not should_apply:
                return

        if not should_apply:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Preview complete: {len(planned)} provider(s) to import, "
                    f"{skipped_count} left unchanged. No changes were written; re-run "
                    "with --apply to import missing providers."
                )
            )
            return

        imported_count = 0
        with transaction.atomic():
            for values in planned:
                if AIProviderConfig.objects.filter(
                    provider_type=values["provider_type"]
                ).exists():
                    continue
                AIProviderHandler.create_provider(
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
            self.style.SUCCESS(f"Imported {imported_count} missing provider(s).")
        )

    @staticmethod
    def _environment_variables(config: dict[str, Any]) -> list[str]:
        names = [config["api_key"]] if config["api_key"] else []
        names.append(config["models"])
        names.extend(config["extra_settings"].values())
        return names
