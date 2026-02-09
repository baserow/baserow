from django.contrib.auth import get_user_model


def setup_user_in_sentry(user):
    """
    This function sets the user in the Sentry context. This is useful for debugging
    and error tracking, and ensure no sensitive information is sent to Sentry.

    :param user: The user that needs to be set in the Sentry context.
    """

    from sentry_sdk import set_user

    set_user({"id": user.id})


def patch_user_model_str():
    """
    This function patches the user model to return the user id instead of the email, to
    ensure no sensitive user information is sent to Sentry.
    """

    User = get_user_model()
    User.__str__ = lambda self: str(self.id)
