class DashboardFilterDoesNotExist(Exception):
    """The requested filter is missing or is in the trash."""


class InvalidDashboardFilterConfiguration(Exception):
    """The selected operator is not compatible with the filter type."""


class InvalidDashboardFilterValues(Exception):
    """Selections are malformed or exceed the dashboard's selection budget."""

    def __init__(self, message, code="invalid_values"):
        super().__init__(message)
        self.code = code


class InvalidDashboardFilterOrder(Exception):
    """The order contains duplicate IDs or filters outside the dashboard."""


class DashboardFilterOptionsExpired(Exception):
    """The option page belongs to an expired or changed filter snapshot."""


class DashboardFilterOptionsTooLarge(Exception):
    """Resolving a calculated option formula would exceed its input budget."""
