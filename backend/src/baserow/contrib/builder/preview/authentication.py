from rest_framework.authentication import BaseAuthentication

from baserow.api.utils import map_exceptions
from baserow.contrib.builder.api.preview.errors import (
    ERROR_BUILDER_PREVIEW_SESSION_INVALID,
)
from baserow.contrib.builder.preview import (
    BUILDER_PREVIEW_HEADER,
    BuilderPreviewGrantHandler,
    BuilderPreviewGrantInvalid,
    get_builder_preview_cookie_name,
)
from baserow.contrib.builder.preview.exceptions import BuilderPreviewSessionInvalid


class BuilderPreviewAuthentication(BaseAuthentication):
    def authenticate(self, request):
        with map_exceptions(
            {BuilderPreviewSessionInvalid: ERROR_BUILDER_PREVIEW_SESSION_INVALID}
        ):
            token = request.COOKIES.get(get_builder_preview_cookie_name())
            if not token:
                if request.headers.get(BUILDER_PREVIEW_HEADER, "").lower() == "true":
                    raise BuilderPreviewSessionInvalid
                return None

            try:
                actor = BuilderPreviewGrantHandler().actor_from_token(token)
            except BuilderPreviewGrantInvalid as exc:
                raise BuilderPreviewSessionInvalid from exc

            return actor, None
