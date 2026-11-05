from importlib import import_module

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from baserow.core.models import SubjectRollout
from baserow.core.registries import subject_type_registry


class Command(BaseCommand):
    help = (
        "Reconcile retained identities and optionally activate Agent field references."
    )

    def add_arguments(self, parser):
        parser.add_argument("--enable-agent-references", action="store_true")

    def handle(self, *args, **options):
        """Run bounded reconciliation and verify the activation invariant."""
        migration = import_module("baserow.core.migrations.0137_backfill_subjects")
        with connection.schema_editor(atomic=False) as schema_editor:
            migration.backfill_subjects(apps, schema_editor)
        if any(
            subject_type.has_invalid_persistent_subjects()
            for subject_type in subject_type_registry.get_all()
            if subject_type.supports_persistent_subjects
        ):
            raise CommandError("Live actors are missing synchronized Subjects.")
        if options["enable_agent_references"]:
            SubjectRollout.objects.update_or_create(
                pk=1, defaults={"agent_references_enabled": True}
            )
        self.stdout.write(self.style.SUCCESS("Subjects reconciled and verified."))
