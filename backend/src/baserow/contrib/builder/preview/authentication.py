from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from baserow.contrib.builder.preview import (
    BuilderPreviewGrantHandler,
    BuilderPreviewGrantInvalid,
    get_builder_preview_cookie_name,
)


class BuilderPreviewAuthentication(BaseAuthentication):
    def authenticate(self, request):
        token = request.COOKIES.get(get_builder_preview_cookie_name())
        if not token:
            return None

        try:
            actor = BuilderPreviewGrantHandler().actor_from_token(token)
        except BuilderPreviewGrantInvalid as exc:
            raise AuthenticationFailed("Invalid builder preview grant") from exc

        return actor, None
