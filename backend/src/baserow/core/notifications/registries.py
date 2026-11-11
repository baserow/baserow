from abc import ABCMeta, abstractmethod
from typing import Optional

from baserow.core.exceptions import (
    InstanceTypeAlreadyRegistered,
    InstanceTypeDoesNotExist,
)
from baserow.core.registry import (
    CustomFieldsRegistryMixin,
    Instance,
    MapAPIExceptionsInstanceMixin,
    ModelRegistryMixin,
    Registry,
)
from baserow.core.utils import get_embedded_share_url

from .models import Notification


class NotificationType(MapAPIExceptionsInstanceMixin, Instance):
    model_class = Notification
    include_in_notifications_email = False

    def get_web_frontend_url(self, notification: Notification) -> Optional[str]:
        """
        Can optionally return a public URL related to the notification. This is
        typically used when the user wants to get more information about the
        notification.

        :param notification: The notification for which we want to generate the URL.
        :return: The generated URL as string, or None if not compatible.
        """

        return None


class EmailNotificationTypeMixin(metaclass=ABCMeta):
    """
    A mixin for notification types that can be sent by email, which provides the
    methods needed to render a title and an optional description in the email message.
    """

    include_in_notifications_email = True

    has_web_frontend_route = False
    """
    If `True`, then the notification will be clickable in the email. Note that this
    will only work if a route is defined in the web-frontend.
    """

    @classmethod
    @abstractmethod
    def get_notification_title_for_email(cls, notification, context) -> str:
        """
        Returns the translatable string title for the given notification and context.
        """

    @classmethod
    @abstractmethod
    def get_notification_description_for_email(
        cls, notification, context
    ) -> Optional[str]:
        """
        Returns the translatable string description for the given notification
        and context.
        """

    def get_web_frontend_url(self, notification):
        if not self.has_web_frontend_route:
            return None

        # This path must match the one defined in web-frontend/modules/core/routes.js
        return get_embedded_share_url(
            f"notification/{notification.workspace_id}/{notification.id}"
        )


class CliNotificationTypeMixin(metaclass=ABCMeta):
    @classmethod
    @abstractmethod
    def prompt_for_args_in_cli_and_create_notification(cls):
        """
        Prompts the user for any additional arguments needed to create the
        notification from the CLI, and then creates the notification.
        """


class NotificationTypeDoesNotExist(InstanceTypeDoesNotExist):
    """Raised when a notification type with a given identifier does not exist."""


class NotificationTypeAlreadyRegistered(InstanceTypeAlreadyRegistered):
    """Raised when a notification type is already registered."""


class NotificationTypeRegistry(
    CustomFieldsRegistryMixin,
    ModelRegistryMixin[Notification, NotificationType],
    Registry[NotificationType],
):
    """
    The registry that holds all the available job types.
    """

    name = "notification_type"

    does_not_exist_exception_class = NotificationTypeDoesNotExist
    already_registered_exception_class = NotificationTypeAlreadyRegistered


notification_type_registry: NotificationTypeRegistry = NotificationTypeRegistry()
