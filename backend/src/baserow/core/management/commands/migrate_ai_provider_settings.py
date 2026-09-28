from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from baserow.core.ai_provider.constants import (
    AI_PROVIDER_TYPES,
    PROVIDER_ENVIRONMENT_SETTINGS,
)
from baserow.core.ai_provider.legacy_import import (
    SKIPPED_EXISTING,
    ImportPlan,
    PlannedProvider,
    SkippedProvider,
    apply_import_plan,
    plan_instance_import,
    plan_workspace_import,
)
from baserow.core.ai_provider.models import AIProviderConfig, AIProviderModel
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
            plan = plan_instance_import(AIProviderConfig, AIProviderModel)
        else:
            plan = plan_workspace_import(AIProviderConfig, AIProviderModel, Workspace)

        self._report_plan(plan)
        skipped_count = len(plan.skipped)

        if scope == INSTANCE_SCOPE and not plan.planned and not skipped_count:
            self._report_unconfigured_instance_settings()
            if not should_apply:
                return

        if not should_apply:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Preview complete for the {scope} scope: {len(plan.planned)} "
                    f"provider(s) to import, {skipped_count} left unchanged. No "
                    "changes were written; re-run with "
                    f"--scope {scope} --apply to import missing providers."
                )
            )
            return

        with transaction.atomic():
            imported_count = len(
                apply_import_plan(plan, AIProviderConfig, AIProviderModel)
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {imported_count} missing {scope} provider(s)."
            )
        )

    def _report_plan(self, plan: ImportPlan) -> None:
        inheriting_types = set(
            AIProviderConfig.objects.filter(
                workspace__isnull=True,
                provider_type__in={
                    provider.provider_type
                    for provider in plan.planned
                    if provider.workspace_id is not None
                },
            ).values_list("provider_type", flat=True)
        )
        inherited_by_counts = dict(
            AIProviderConfig.objects.filter(
                workspace__isnull=False,
                provider_type__in={
                    provider.provider_type
                    for provider in plan.planned
                    if provider.workspace_id is None
                },
            )
            .values_list("provider_type")
            .annotate(Count("id"))
        )
        for provider in plan.planned:
            self.stdout.write(
                f"{self._prefix(provider)}: import {len(provider.models)} model(s); "
                f"credential set: {'yes' if provider.api_key else 'no'}."
            )
            workspaces_that_will_inherit = inherited_by_counts.get(
                provider.provider_type, 0
            )
            if provider.workspace_id is None and workspaces_that_will_inherit:
                self.stdout.write(
                    self.style.WARNING(
                        f"{self._prefix(provider)}: {workspaces_that_will_inherit} "
                        "workspace(s) with their own provider of this type will now "
                        "also inherit this one. Disable the inherited provider for "
                        "each of them to match what the upgrade migration does."
                    )
                )
            if provider.provider_type in inheriting_types:
                self.stdout.write(
                    self.style.WARNING(
                        f"{self._prefix(provider)}: this workspace will also inherit "
                        "the instance provider of the same type, which its legacy "
                        "settings replaced. The upgrade opts imported workspaces out "
                        "automatically; disable the inherited provider for this "
                        "workspace under its AI providers settings to match."
                    )
                )
        for skipped in plan.skipped:
            if skipped.kind == SKIPPED_EXISTING:
                message = f"keeping existing database configuration ({skipped.reason})."
            elif skipped.workspace_id is None:
                message = f"skipping, {skipped.reason}."
            else:
                message = f"skipping {skipped.reason}."
            self.stdout.write(self.style.WARNING(f"{self._prefix(skipped)}: {message}"))

    @staticmethod
    def _prefix(entry: PlannedProvider | SkippedProvider) -> str:
        provider_name = AI_PROVIDER_TYPES[entry.provider_type]["name"]
        if entry.workspace_id is None:
            return provider_name
        return (
            f"Workspace {entry.workspace_id} ({entry.workspace_name}), {provider_name}"
        )

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
