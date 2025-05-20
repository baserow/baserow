from django.db.models import TextChoices


class SearchTableState(TextChoices):
    """
    Describes if a search table was updated with this table's user data
    """

    NOT_INITED = "not_inited"
    INITED = "inited"
    DONE = "done"
    # useful for testing
    DISABLED = "disabled"
