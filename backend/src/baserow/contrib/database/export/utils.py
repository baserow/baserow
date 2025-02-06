from typing import Optional

from django.contrib.auth.models import AbstractUser

from baserow.contrib.database.views.models import View


def view_is_publicly_exportable(user: Optional[AbstractUser], view: View):
    """
    Checks if a view can be publicly exported for the given user.

    :param user: The (optional) user on whose behalf the check must be completed.
    :param view: The view to check.
    :return: Indicates whether the view is publicly exportable
    """

    return user is None and view and view.allow_public_export and view.public
