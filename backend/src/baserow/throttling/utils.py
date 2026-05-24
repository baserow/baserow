def get_auth_token(request) -> str | None:
    """Extract a JWT or database-Token bearer value from the Authorization header."""

    auth = request.META.get("HTTP_AUTHORIZATION", "")
    head = auth[:6].lower()
    if head.startswith("jwt "):
        return auth[4:]
    if head.startswith("token "):
        return auth[6:]
    return None
