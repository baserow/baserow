from functools import wraps
from typing import Callable, Union

from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK


def requires_published_application(func) -> Union[Callable, Response]:
    """
    A decorator to apply to publicly accessible builder endpoints. If we find that the
    requested page ID doesn't point to a published application, we won't perform any
    further SQL queries and return an empty response.
    """

    @wraps(func)
    def wrapper(view, request, page_id):
        from baserow.contrib.builder.pages.handler import PageHandler

        if not request.user.is_anonymous and not PageHandler().is_published_page(
            page_id
        ):
            return Response([], status=HTTP_200_OK)
        return func(view, request, page_id)

    return wrapper
