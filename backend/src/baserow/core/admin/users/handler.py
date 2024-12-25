from typing import Optional

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Q

from baserow.core.admin.users.exceptions import (
    CannotDeactivateYourselfException,
    CannotDeleteYourselfException,
    UserDoesNotExistException,
)
from baserow.core.exceptions import IsNotAdminError
from baserow.core.signals import before_user_deleted
from baserow.core.user.exceptions import (
    PasswordDoesNotMatchValidation,
    UserAlreadyExist,
)
from baserow.core.user.handler import UserHandler
from baserow.core.user.utils import normalize_email_address

User = get_user_model()


class UserAdminHandler:
    def create_user(
        self,
        requesting_user: User,
        username: str,
        name: str,
        password: str,
        is_active: bool = True,
        is_staff: bool = False,
    ):
        """
        Creates a new user with the provided values if the requesting user has admin
        access. The user will be created, even if the signups are disabled.

        :param requesting_user: The user who is making the request to creata a user, the
            user must be a staff member or else an exception will be raised.
        :param username: New username/email to set for the user.
        :param name: New name to set on the user.
        :param password: New password to securely set for the user.
        :param is_staff: Value used to set if the user is an admin or not.
        :param is_active: Value to disable or enable login for the user.
        """

        self._raise_if_not_permitted(requesting_user)

        user = UserHandler().force_create_user(
            email=username,
            name=name,
            password=password,
            is_staff=is_staff,
            is_active=is_active,
        )

        return user

    def update_user(
        self,
        requesting_user: User,
        user_id: int,
        username: Optional[str] = None,
        name: Optional[str] = None,
        password: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_staff: Optional[bool] = None,
    ):
        """
        Updates a specified user with new attribute values. Will raise an exception
        if a user attempts to de-activate or un-staff themselves.

        :param requesting_user: The user who is making the request to update a user, the
            user must be a staff member or else an exception will
            be raised.
        :param user_id: The id of the user to update, if they do not exist raises a
            UserDoesNotExistException.
        :param is_staff: Optional value used to set if the user is an admin or not.
        :param is_active: Optional value to disable or enable login for the user.
        :param password: Optional new password to securely set for the user.
        :param name: Optional new name to set on the user.
        :param username: Optional new username/email to set for the user.
        :raises PasswordDoesNotMatchValidation: When the provided password value is not
            a valid password.
        :raises UserAlreadyExist: If a user with that username already exists.
        """

        self._raise_if_not_permitted(requesting_user)
        self._raise_if_locking_self_out_of_admin(
            is_active, is_staff, requesting_user, user_id
        )

        try:
            user = User.objects.select_for_update(of=("self",)).get(id=user_id)
        except User.DoesNotExist:
            raise UserDoesNotExistException()

        if is_staff is not None:
            user.is_staff = is_staff
        if is_active is not None:
            user.is_active = is_active
        if password is not None:
            try:
                validate_password(password, user)
            except ValidationError as e:
                raise PasswordDoesNotMatchValidation(e.messages)
            user.set_password(password)
        if name is not None:
            user.first_name = name
        if username is not None:
            email = normalize_email_address(username)
            user_query = User.objects.filter(
                Q(email=email) | Q(username=email), ~Q(id=user.id)
            )
            if email != user.email and user_query.exists():
                raise UserAlreadyExist(
                    f"A user with the username {email} already exists."
                )

            user.email = email
            user.username = email

        user.save()
        return user

    @staticmethod
    def _raise_if_locking_self_out_of_admin(
        is_active, is_staff, requesting_user, user_id
    ):
        """
        Raises an exception if the requesting_user is about to lock themselves out of
        the admin area of Baserow by either turning off their staff status or disabling
        their account.
        """

        is_setting_staff_to_false = is_staff is not None and not is_staff
        is_setting_active_to_false = is_active is not None and not is_active
        if user_id == requesting_user.id and (
            is_setting_staff_to_false or is_setting_active_to_false
        ):
            raise CannotDeactivateYourselfException()

    def delete_user(self, requesting_user: User, user_id: int):
        """
        Deletes a specified user, raises an exception if you attempt to delete yourself.

        :param requesting_user: The user who is making the delete request , the
            user must be a staff member or else an exception will
            be raised.
        :param user_id: The id of the user to update, if they do not exist raises a
            UnknownUserException.
        """

        self._raise_if_not_permitted(requesting_user)

        if requesting_user.id == user_id:
            raise CannotDeleteYourselfException()

        try:
            user = User.objects.get(id=user_id)

            before_user_deleted.send(self, user=user)

            user.delete()
        except User.DoesNotExist:
            raise UserDoesNotExistException()

    @staticmethod
    def _raise_if_not_permitted(requesting_user):
        if not requesting_user.is_staff:
            raise IsNotAdminError()
