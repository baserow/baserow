class DashboardDoesNotExist(Exception):
    """Raised when the dashboard application doesn't exist."""


class NoAuthorizationToPublicDashboard(Exception):
    """
    Raised when a password protected public dashboard is accessed without a valid
    authorization token.
    """
