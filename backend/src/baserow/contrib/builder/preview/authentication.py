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
            header = request.headers.get(BUILDER_PREVIEW_HEADER)
            if header is None:
                return None

            try:
                builder_id = int(header)
            except (TypeError, ValueError) as exc:
                raise BuilderPreviewSessionInvalid from exc

            token = request.COOKIES.get(get_builder_preview_cookie_name(builder_id))
            if not token:
                raise BuilderPreviewSessionInvalid

            try:
                actor = BuilderPreviewGrantHandler().actor_from_token(token)
            except BuilderPreviewGrantInvalid as exc:
                raise BuilderPreviewSessionInvalid from exc

            if actor.builder_id != builder_id:
                raise BuilderPreviewSessionInvalid

            return actor, None
