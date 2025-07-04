from django.db.models import TextChoices


class SearchTableState(TextChoices):
    """
    Describes if a search table was updated with this table's user data
    """

    READY = "ready"
    # useful for testing
    DISABLED = "disabled"
