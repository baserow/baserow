from typing import Callable

from django.http import HttpRequest, HttpResponse
from django.urls import Resolver404, resolve

from opentelemetry import baggage, context

from baserow.api.sessions import get_user_remote_ip_address_from_request


class BaserowOTELMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        try:
            match = getattr(request, "resolver_match", None) or resolve(request.path)
            route = getattr(match, "route", None)
        except Resolver404:
            route = None

        ctx = context.get_current()
        if route:
            ctx = baggage.set_baggage("http.route", route, context=ctx)

        client_ip = get_user_remote_ip_address_from_request(request)
        if client_ip:
            ctx = baggage.set_baggage("client.address", client_ip, context=ctx)

        if route or client_ip:
            token = context.attach(ctx)
            try:
                return self.get_response(request)
            finally:
                context.detach(token)
        else:
            return self.get_response(request)
