from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest
from django.utils.deprecation import MiddlewareMixin
from django.utils.functional import SimpleLazyObject

from baserow.api.user_sources.authentication import UserSourceJSONWebTokenAuthentication
from baserow.core.user_sources.user_source_user import UserSourceUser


def get_user_source_authentication_header(request: HttpRequest) -> str | None:
    if getattr(getattr(request, "user", None), "is_builder_preview_actor", False):
        return "Authorization"
    return None


class AddUserSourceUserMiddleware(MiddlewareMixin):
    """
    This django middleware adds the `user_source_user` that can be used by a
    data provider later.
    If the authenticated user is an instance of the UserSourceUser class we use this
    one otherwise we try to authenticate one with the
    secondary header used for "double" authentication.
    Preview authentication uses the regular Authorization header as the secondary
    user source header because the primary builder preview actor comes from the
    HttpOnly preview cookie.
    That way we can have the permission of the currently logged in user and use the
    data of the user source user.
    """

    def process_request(self, request):
        def get_user_source_user():
            if isinstance(getattr(request, "user", None), UserSourceUser):
                # We already have a UserSourceUser so we use it
                return request.user
            else:
                # Otherwise we try to authenticate with the secondary user source
                # header.
                authentication_header = get_user_source_authentication_header(request)
                result = UserSourceJSONWebTokenAuthentication(
                    use_user_source_authentication_header=True,
                    authentication_header=authentication_header,
                ).authenticate(request)

                if result is None:
                    return AnonymousUser()
                return result[0]

        request.user_source_user = SimpleLazyObject(get_user_source_user)
