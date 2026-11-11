from typing import Optional

from django.conf import settings

from rest_framework.request import Request


def get_public_dashboard_authorization_token(request: Request) -> Optional[str]:
    """
    Returns the token that grants access to a password protected public dashboard,
    if the request carries one.

    :param request: The request.
    :return: The public dashboard access token or None.
    """

    auth_header = request.headers.get(
        settings.PUBLIC_DASHBOARD_AUTHORIZATION_HEADER, None
    )
    try:
        _, token = auth_header.split(" ", 1)
    except (AttributeError, ValueError):
        return None
    return token
