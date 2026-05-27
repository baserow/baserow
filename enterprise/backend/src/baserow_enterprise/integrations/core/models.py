from baserow.core.formula.field import FormulaField
from baserow.core.services.models import Service


class CoreCodeService(Service):
    """
    A service for executing arbitrary code.
    """

    code = FormulaField(blank=True, help_text="The code to execute.")
