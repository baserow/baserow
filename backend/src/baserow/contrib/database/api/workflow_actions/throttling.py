from django.conf import settings

from baserow.throttling.handler import RateLimitThrottle


class ButtonFieldDispatchUserRateThrottle(RateLimitThrottle):
    """
    Limits how often one user may click buttons that reach outside Baserow.

    Keyed on the user, not the button: they can spread their clicks over as
    many buttons, tables and workspaces as they like. Staff are exempt, as they
    are from the other user rate limits here, so an instance admin can still
    work while a limit is in force; the workspace limit still applies to them.
    """

    scope = "button_field_dispatch_user"

    def get_rate_limits(self, request):
        """
        :param request: The click being counted.
        :return: The configured user limits. Empty switches the throttle off.
        """

        return settings.DATABASE_BUTTON_DISPATCH_USER_RATE_LIMITS

    def get_ident(self, request) -> str | None:
        """
        :param request: The click being counted.
        :return: The user's id, or `None` to exempt the click. Anonymous
            callers have nobody to count against and the view refuses them
            anyway; staff are exempt so an admin can work through a limit.
        """

        user = request.user

        if not user.is_authenticated or user.is_staff:
            return None

        return str(user.id)


class ButtonFieldDispatchWorkspaceRateThrottle(RateLimitThrottle):
    """
    Limits how often a workspace's buttons may reach outside Baserow.

    The workspace is not in the request, so the view hands it in.
    """

    scope = "button_field_dispatch_workspace"

    def __init__(self, workspace_id: int):
        """
        :param workspace_id: The workspace the clicked button belongs to. The
            request does not carry it, so the view passes it in.
        """

        super().__init__()
        self.workspace_id = workspace_id

    def get_rate_limits(self, request):
        """
        :param request: The click being counted.
        :return: The configured workspace limits. Empty switches the throttle
            off.
        """

        return settings.DATABASE_BUTTON_DISPATCH_WORKSPACE_RATE_LIMITS

    def get_ident(self, request) -> str | None:
        """
        :param request: Unused; the identity comes from `__init__`, so every
            member shares one budget.
        :return: The workspace's id. Never `None`: no click is exempt, staff
            included.
        """

        return str(self.workspace_id)
