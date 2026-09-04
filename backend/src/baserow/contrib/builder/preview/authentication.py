from rest_framework.authentication import BaseAuthentication

from baserow.api.utils import map_exceptions
from baserow.contrib.builder.api.preview.errors import (
    ERROR_BUILDER_PREVIEW_SESSION_INVALID,
)
from baserow.contrib.builder.preview import (
    BuilderPreviewGrantHandler,
    BuilderPreviewGrantInvalid,
    get_builder_preview_cookie_name,
)
from baserow.contrib.builder.preview.exceptions import BuilderPreviewSessionInvalid


class BuilderPreviewAuthentication(BaseAuthentication):
    """
    Authenticate a builder-scoped preview API request.

    Every protected preview route contains ``builder_id``. The browser uses it
    to select the path-scoped cookie, and the signed actor must identify the
    same builder.
    """

    def get_builder_id(self, request):
        try:
            return int(request.parser_context["kwargs"]["builder_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise BuilderPreviewSessionInvalid from exc

    def authenticate(self, request):
        with map_exceptions(
            {BuilderPreviewSessionInvalid: ERROR_BUILDER_PREVIEW_SESSION_INVALID}
        ):
            builder_id = self.get_builder_id(request)
            token = request.COOKIES.get(get_builder_preview_cookie_name())
            if not token:
                raise BuilderPreviewSessionInvalid

            try:
                actor = BuilderPreviewGrantHandler().actor_from_token(token)
            except BuilderPreviewGrantInvalid as exc:
                raise BuilderPreviewSessionInvalid from exc

            if actor.builder_id != builder_id:
                raise BuilderPreviewSessionInvalid

            return actor, None
