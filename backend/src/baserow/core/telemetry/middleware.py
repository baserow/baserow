from typing import Callable

from django.http import HttpRequest, HttpResponse
from django.urls import Resolver404, resolve

from opentelemetry import baggage, context


class BaserowOTELMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        try:
            match = getattr(request, "resolver_match", None) or resolve(request.path)
            route = getattr(match, "route", None)
        except Resolver404:
            route = None

        if route:
            ctx = context.get_current()
            new_ctx = baggage.set_baggage("http.route", route, context=ctx)
            token = context.attach(new_ctx)
            try:
                return self.get_response(request)
            finally:
                context.detach(token)
        else:
            return self.get_response(request)
