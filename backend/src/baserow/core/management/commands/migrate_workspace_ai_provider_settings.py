from django.core.management.base import BaseCommand
from django.db import transaction

from baserow.core.ai_provider.constants import PROVIDER_ENVIRONMENT_SETTINGS
from baserow.core.ai_provider.exceptions import InvalidAIProviderSettings
from baserow.core.ai_provider.handler import AIProviderHandler
from baserow.core.ai_provider.models import AIProviderConfig
from baserow.core.ai_provider.provider_types import (
    normalize_model_identifiers,
    validate_provider_settings,
)
from baserow.core.models import Workspace


class Command(BaseCommand):
    help = (
        "Preview or apply an import of legacy workspace AI settings into missing "
        "workspace-owned database providers."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply the import atomically. Without this flag it is read-only.",
        )

    def handle(self, *args, **options):
        should_apply = options["apply"]
        existing = set(
            AIProviderConfig.objects.filter(workspace__isnull=False).values_list(
                "workspace_id", "provider_type"
            )
        )
        planned = []
        skipped = 0

        for workspace in Workspace.objects.only(
            "id", "name", "generative_ai_models_settings"
        ).iterator():
            legacy_settings = workspace.generative_ai_models_settings or {}
            for provider_type, config in PROVIDER_ENVIRONMENT_SETTINGS.items():
                values = legacy_settings.get(provider_type)
                if not isinstance(values, dict) or not any(values.values()):
                    continue
                if (workspace.id, provider_type) in existing:
                    skipped += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"Workspace {workspace.id} ({workspace.name}), "
                            f"{config['name']}: keeping existing database "
                            "configuration."
                        )
                    )
                    continue

                api_key = str(values.get("api_key") or "")
                models = normalize_model_identifiers(values.get("models"))
                extra_settings = {
                    name: values[name]
                    for name in config["extra_settings"]
                    if values.get(name) not in (None, "")
                }
                try:
                    validate_provider_settings(
                        provider_type,
                        api_key,
                        extra_settings,
                        models,
                        require_credentials=True,
                    )
                except InvalidAIProviderSettings as exc:
                    skipped += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"Workspace {workspace.id} ({workspace.name}), "
                            f"{config['name']}: skipping incomplete legacy settings "
                            f"({exc})."
                        )
                    )
                    continue

                planned.append(
                    {
                        "workspace": workspace,
                        "provider_type": provider_type,
                        "api_key": api_key,
                        "extra_settings": extra_settings,
                        "models": models,
                    }
                )
                self.stdout.write(
                    f"Workspace {workspace.id} ({workspace.name}), "
                    f"{config['name']}: import {len(models)} model(s); credential "
                    f"set: {'yes' if api_key else 'no'}."
                )

        if not should_apply:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Preview complete: {len(planned)} provider(s) to import, "
                    f"{skipped} left unchanged. No changes were written; re-run "
                    "with --apply to import missing providers."
                )
            )
            return

        imported = 0
        with transaction.atomic():
            for values in planned:
                workspace = values["workspace"]
                provider_type = values["provider_type"]
                if AIProviderConfig.objects.filter(
                    workspace=workspace, provider_type=provider_type
                ).exists():
                    continue
                AIProviderHandler.create_provider(
                    workspace=workspace,
                    provider_type=provider_type,
                    api_key=values["api_key"],
                    extra_settings=values["extra_settings"],
                    models_data=[
                        {"model_identifier": identifier}
                        for identifier in values["models"]
                    ],
                )
                imported += 1

        self.stdout.write(
            self.style.SUCCESS(f"Imported {imported} missing provider(s).")
        )
