from django.core.management.base import BaseCommand
from django.db import transaction

from baserow.contrib.database.fields.dependencies.handler import FieldDependencyHandler
from baserow.contrib.database.fields.field_cache import FieldCache
from baserow.contrib.database.fields.models import FormulaField


class Command(BaseCommand):
    help = (
        "Resets a single formula field to have the specified formula. Does not "
        "update any dependant formulas."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "field_id",
            type=int,
            help="The ID of the formula field to reset.",
        )
        parser.add_argument(
            "formula",
            type=str,
            help="The new formula to reset the field to.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        field_id = options["field_id"]
        new_formula = options["formula"]
        formula = FormulaField.objects.get(id=field_id)
        formula.formula = new_formula
        formula.save(recalculate=True, raise_if_invalid=True)
        FieldDependencyHandler().rebuild_dependencies([formula], FieldCache())
