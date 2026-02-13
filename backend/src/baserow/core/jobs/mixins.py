from typing import Any

from django.contrib.auth.models import AbstractUser
from django.db import models

from baserow.api.sessions import (
    get_client_undo_redo_action_group_id,
    get_untrusted_client_session_id,
    get_user_remote_addr_ip,
    set_client_undo_redo_action_group_id,
    set_untrusted_client_session_id,
    set_user_remote_addr_ip,
)


class JobWithUserDataMixin(models.Model):
    """
    This mixin permits to add information about the user session to the job in
    order to handle correctly the undo/redo functionality and the signals
    updates. NOTE: This is an abstract mixin. Extend from JobWithWebsocketId
    and JobWithUndoRedoIds in your final JobTypes classes instead.
    """

    def save_user_data_if_not_present(self, user: AbstractUser) -> None:
        """
        Save the user session in the job so to be able to restore.
        Call this in a request context and not from a celery job or other contexts.

        :param user: The user to save the data for.
        """

        # call _save_user_data_if_not_present for all the subclasses that define it.
        for cls in self.__class__.__bases__:
            if hasattr(cls, "_save_user_data_if_not_present"):
                cls._save_user_data_if_not_present(self, self.user)

    def restore_user_data_if_present(self, user: AbstractUser) -> None:
        """
        Restore the user session in the job so to be able to restore.

        :param user: The user to restore the data for.
        """

        # call _save_user_data_if_not_present for all the subclasses that define it.
        for cls in self.__class__.__bases__:
            if hasattr(cls, "_restore_user_data_if_present"):
                cls._restore_user_data_if_present(self, user)

    def save(self, *args, **kwargs):
        self.save_user_data_if_not_present(self.user)
        return super().save(*args, **kwargs)

    def __getattribute__(self, name: str) -> Any:
        value = super().__getattribute__(name)

        if name == "user":
            user = value
            self.restore_user_data_if_present(user)

        return value

    class Meta:
        abstract = True


class JobWithUserIpAddress(JobWithUserDataMixin):
    user_ip_address = models.GenericIPAddressField(
        null=True, help_text="The user IP address."
    )

    def _save_user_data_if_not_present(self, user: AbstractUser) -> None:
        """
        Save the user session in the job so to be able to restore.
        Call this in a request context and not from a celery job or other contexts.

        :param user: The user to save the data for.
        """

        if self.user_ip_address is None:
            self.user_ip_address = get_user_remote_addr_ip(user)

    def _restore_user_data_if_present(self, user: AbstractUser) -> None:
        """
        Restore the user session in the job so to be able to restore.

        :param user: The user to restore the data for.
        """

        if self.user_ip_address is not None:
            set_user_remote_addr_ip(user, self.user_ip_address)

    class Meta:
        abstract = True


class JobWithWebsocketId(JobWithUserDataMixin):
    """
    This mixin add the websocket id to the job so that actions and handlers can
    use it to send websocket messages to the client accordingly.
    """

    user_websocket_id = models.CharField(
        max_length=36,
        null=True,
        help_text="The user websocket uuid needed to manage signals sent correctly.",
    )

    def _save_user_data_if_not_present(self, user: AbstractUser) -> None:
        """
        Save the user session in the job so to be able to restore.
        Call this in a request context and not from a celery job or other contexts.

        :param user: The user to save the data for.
        """

        if self.user_websocket_id is None:
            self.user_websocket_id = getattr(user, "web_socket_id", None)

    def _restore_user_data_if_present(self, user: AbstractUser) -> None:
        """
        Restore the user session in the job so to be able to restore.

        :param user: The user to restore the data for.
        """

        if self.user_websocket_id is not None:
            user.web_socket_id = self.user_websocket_id

    class Meta:
        abstract = True


class JobWithUndoRedoIds(JobWithUserDataMixin):
    """
    This mixin add the ids needed for the undo/redo functionality to
    work with the code called from the job.
    """

    user_session_id = models.CharField(
        max_length=36,
        null=True,
        help_text="The user session uuid needed for undo/redo functionality.",
    )
    user_action_group_id = models.CharField(
        max_length=36,
        null=True,
        help_text="The user session uuid needed for undo/redo action group functionality.",
    )

    def _save_user_data_if_not_present(self, user: AbstractUser) -> None:
        """
        Save the user session in the job so to be able to restore.
        Call this in a request context and not from a celery job or other contexts.

        :param user: The user to save the data for.
        """

        if self.user_session_id is None:
            self.user_session_id = get_untrusted_client_session_id(user)

        if self.user_action_group_id is None:
            self.user_action_group_id = get_client_undo_redo_action_group_id(user)

    def _restore_user_data_if_present(self, user: AbstractUser) -> None:
        """
        Restore the user session in the job so to be able to restore.

        :param user: The user to restore the data for.
        """

        if self.user_session_id is not None:
            set_untrusted_client_session_id(user, self.user_session_id)

        if self.user_action_group_id is not None:
            set_client_undo_redo_action_group_id(user, self.user_action_group_id)

    class Meta:
        abstract = True
