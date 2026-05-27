from django.db import models

from baserow.core.formula.field import FormulaField
from baserow.core.services.models import Service


class CoreCodeService(Service):
    """
    A service for executing arbitrary code.
    """

    code = models.TextField(blank=True, help_text="The code to execute.")


class CoreCodeServiceInjection(models.Model):
    """
    A value extracted from the dispatch context and injected into the code context.
    """

    service = models.ForeignKey(
        CoreCodeService, on_delete=models.CASCADE, related_name="injections"
    )
    name = models.CharField(
        max_length=255,
        help_text="The variable name to use in the code executor context.",
    )
    formula = FormulaField(
        blank=True,
        help_text="The formula used to extract the variable value from the context.",
    )
