from copy import deepcopy

from django.contrib.auth.models import AbstractUser

from baserow.contrib.database.table.cache import invalidate_table_in_model_cache
from baserow.contrib.database.views.exceptions import CannotShareViewTypeError
from baserow.contrib.database.views.models import View
from baserow.contrib.database.views.registries import view_type_registry
from baserow.contrib.database.views.signals import view_updated
from baserow.core.exceptions import IsNotAdminError


class ViewsAdminHandler:
    def update_view_public(
        self, requesting_user: AbstractUser, view: View, public: bool
    ) -> View:
        """
        Changes whether the provided view is publicly shared. This deliberately skips
        the workspace permission checks because the requesting staff user is typically
        not a member of the workspace. It's used by instance admins to intervene when a
        publicly shared view is abused.

        :param requesting_user: The staff user on whose behalf the view is updated.
        :param view: The view that must be updated.
        :param public: Whether the view must be publicly shared.
        :raises IsNotAdminError: When the requesting user is not staff.
        :raises CannotShareViewTypeError: When the view type doesn't support sharing.
        :return: The updated view instance.
        """

        self._raise_if_not_permitted(requesting_user)
        self._raise_if_not_shareable(view)

        view = view.specific
        old_view = deepcopy(view)
        view.public = public
        view.save()

        view_updated.send(self, view=view, user=requesting_user, old_view=old_view)

        return view

    def rotate_view_slug(self, requesting_user: AbstractUser, view: View) -> View:
        """
        Rotates the slug of the provided view, permanently invalidating the current
        public URL. This deliberately skips the workspace permission checks because
        the requesting staff user is typically not a member of the workspace.

        :param requesting_user: The staff user on whose behalf the view is updated.
        :param view: The view whose slug must be rotated.
        :raises IsNotAdminError: When the requesting user is not staff.
        :raises CannotShareViewTypeError: When the view type doesn't support sharing.
        :return: The updated view instance.
        """

        self._raise_if_not_permitted(requesting_user)
        self._raise_if_not_shareable(view)

        view = view.specific
        old_view = deepcopy(view)
        view.rotate_slug()
        view.save()

        # Invalidate the model cache because fields could be depending on that specific
        # model slug, like the edit row link field.
        invalidate_table_in_model_cache(view.table_id)

        view_updated.send(self, view=view, user=requesting_user, old_view=old_view)

        return view

    @staticmethod
    def _raise_if_not_permitted(requesting_user: AbstractUser):
        if not requesting_user.is_staff:
            raise IsNotAdminError()

    @staticmethod
    def _raise_if_not_shareable(view: View):
        view_type = view_type_registry.get_by_model(view.specific_class)
        if not view_type.can_share:
            raise CannotShareViewTypeError()
