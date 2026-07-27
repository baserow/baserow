from django.contrib.auth.models import AnonymousUser
from django.utils.deprecation import MiddlewareMixin
from django.utils.functional import SimpleLazyObject

from baserow.api.user_sources.authentication import UserSourceJSONWebTokenAuthentication
from baserow.core.user_sources.user_source_user import UserSourceUser


class AddUserSourceUserMiddleware(MiddlewareMixin):
    """
    This django middleware adds the `user_source_user` that can be used by a
    data provider later.
    If the authenticated user is an instance of the UserSourceUser class we use this
    one otherwise we try to authenticate one with the
    secondary header used for "double" authentication.
    Primary actors can override the header containing the user source token with
    `user_source_authentication_header`.
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
                authentication_header = getattr(
                    getattr(request, "user", None),
                    "user_source_authentication_header",
                    None,
                )
                result = UserSourceJSONWebTokenAuthentication(
                    use_user_source_authentication_header=True,
                    authentication_header=authentication_header,
                ).authenticate(request)

                if result is None:
                    return AnonymousUser()
                return result[0]

        request.user_source_user = SimpleLazyObject(get_user_source_user)
