from rest_framework import HTTP_HEADER_ENCODING
from rest_framework.authentication import get_authorization_header


def get_auth_token(request) -> str | None:
    """
    Extracts the token from the request's Authorization header, if present.
    """

    auth = get_authorization_header(request).decode(HTTP_HEADER_ENCODING).split(" ", 1)
    if len(auth) == 2 and auth[0].lower() in ("jwt", "token"):
        return auth[1]
    return None
