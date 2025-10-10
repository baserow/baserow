from typing import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.urls import is_valid_path

from rest_framework import status

from baserow.config.db_routers import clear_db_state
from baserow.core.handler import CoreHandler
from baserow.throttling import ConcurrentUserRequestsThrottle


def json_error_404_add_trailing_slash(path: str) -> HttpResponse:
    """
    Return a nicer and informative error in case the url is
    valid adding a trailing slash to the end.
    The same error message is returned both for safe method that
    could be redirected (GET, HEAD, OPTIONS) and for unsafe methods
    where redirection with data is not possible due to security limitations.
    """

    return JsonResponse(
        {
            "error": "URL_TRAILING_SLASH_MISSING",
            "detail": (
                "A valid URL must end with a trailing slash. "
                f"Please, redirect requests to {path}/"
            ),
        },
        status=status.HTTP_404_NOT_FOUND,
    )


def json_error_404_not_found(path: str) -> HttpResponse:
    return JsonResponse(
        {"error": "URL_NOT_FOUND", "detail": f"URL {path} not found."},
        status=status.HTTP_404_NOT_FOUND,
    )


def json_is_accepted(request: HttpRequest) -> bool:
    accept_headers = request.headers.get("accept", "")
    return "application/json" in accept_headers or accept_headers in ["*/*", ""]


class BaserowCustomHttp404Middleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)

        if response.status_code == 404:
            path, urlconf = request.path_info, getattr(request, "urlconf", None)
            if (
                is_valid_path(path, urlconf)
                or settings.DEBUG
                and not json_is_accepted(request)
            ):
                return response
            elif is_valid_path(f"{path}/", urlconf):
                return json_error_404_add_trailing_slash(path)
            else:
                return json_error_404_not_found(path)
        return response


class ConcurrentUserRequestsMiddleware:
    """
    This middleware is used as counterpart of the
    `ConcurrentUserRequestsThrottle` to remove the request id from the throttle
    cache once processed. This is needed because the throttle is
    not aware of the request lifecycle and therefore can't remove it by itself.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        ConcurrentUserRequestsThrottle.on_request_processed(request)
        return response


class ClearContextMiddleware:
    """
    This middleware is used to clear the context after the response has been returned.
    Such context can be used i.e. to store the current workspace id
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        try:
            response = self.get_response(request)
        finally:
            # Make sure that the context is cleared after the response has been
            # returned regardless of any exceptions that might have been raised.
            CoreHandler().clear_context()
        return response


class ClearDBStateMiddleware:
    """
    Clearing the db state after every request, so that if a read-only replica is
    configured, it will correctly use that one instead of the writer.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        clear_db_state()
        return response
