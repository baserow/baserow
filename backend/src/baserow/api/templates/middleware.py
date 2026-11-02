from typing import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from baserow.core.user_templates.private_link import private_link_token


class TemplatePrivateLinkMiddleware:
    """
    Makes the token of the private link of a user template, sent in its header,
    available to the permission checks of the request, which don't get the request
    itself, see `get_private_link_token`.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        with private_link_token(
            request.headers.get(settings.TEMPLATE_PRIVATE_LINK_HEADER)
        ):
            return self.get_response(request)
