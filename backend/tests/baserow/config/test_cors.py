from django.http import HttpResponse
from django.test import RequestFactory, override_settings

from corsheaders.middleware import CorsMiddleware

from baserow.middleware import BaserowCredentialedCorsMiddleware


def get_cors_response(origin):
    request = RequestFactory().get(
        "/api/builder/preview/current/",
        HTTP_ORIGIN=origin,
    )

    middleware = BaserowCredentialedCorsMiddleware(
        CorsMiddleware(lambda _request: HttpResponse())
    )
    return middleware(request)


def get_cors_preflight_response(origin, requested_headers):
    request = RequestFactory().options(
        "/api/builder/preview/current/",
        HTTP_ORIGIN=origin,
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS=requested_headers,
    )

    middleware = BaserowCredentialedCorsMiddleware(
        CorsMiddleware(lambda _request: HttpResponse())
    )
    return middleware(request)


@override_settings(
    CORS_ORIGIN_ALLOW_ALL=True,
    CORS_ALLOW_CREDENTIALS=False,
    BASEROW_CORS_ALLOWED_CREDENTIAL_ORIGINS=["https://preview.example.com"],
)
def test_trusted_origin_gets_credentialed_cors_headers():
    response = get_cors_response("https://preview.example.com")

    assert response["Access-Control-Allow-Origin"] == "https://preview.example.com"
    assert response["Access-Control-Allow-Credentials"] == "true"
    assert "origin" in response["Vary"].lower()


@override_settings(
    CORS_ORIGIN_ALLOW_ALL=True,
    CORS_ALLOW_CREDENTIALS=False,
    BASEROW_CORS_ALLOWED_CREDENTIAL_ORIGINS=["https://preview.example.com"],
)
def test_arbitrary_origin_keeps_non_credentialed_cors_headers():
    response = get_cors_response("https://custom-domain.example.com")

    assert response["Access-Control-Allow-Origin"] == "*"
    assert "Access-Control-Allow-Credentials" not in response


@override_settings(
    CORS_ORIGIN_ALLOW_ALL=True,
    CORS_ALLOW_CREDENTIALS=False,
    BASEROW_CORS_ALLOWED_CREDENTIAL_ORIGINS=["https://preview.example.com"],
)
def test_trusted_origin_preflight_accepts_builder_preview_header():
    response = get_cors_preflight_response(
        "https://preview.example.com", "x-baserow-builder-preview"
    )

    allowed_headers = {
        header.strip().lower()
        for header in response["Access-Control-Allow-Headers"].split(",")
    }
    assert "x-baserow-builder-preview" in allowed_headers
    assert response["Access-Control-Allow-Credentials"] == "true"
