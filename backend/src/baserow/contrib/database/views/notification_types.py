from dataclasses import asdict, dataclass
from typing import Any, Dict

from django.contrib.auth.models import AnonymousUser
from django.dispatch import receiver
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from baserow.contrib.database.views.operations import (
    CanReceiveNotificationOnSubmitFormViewOperationType,
)
from baserow.core.handler import CoreHandler
from baserow.core.notifications.handler import NotificationHandler
from baserow.core.notifications.registries import (
    EmailNotificationTypeMixin,
    NotificationType,
)

from .signals import form_submitted


@dataclass
class FormSubmittedNotificationData:
    form_id: int
    form_name: str
    table_id: int
    table_name: str
    database_id: int
    row_id: int
    values: Dict[str, Any]


class FormSubmittedNotificationType(EmailNotificationTypeMixin, NotificationType):
    type = "form_submitted"
    has_web_frontend_route = True

    @classmethod
    def create_form_submitted_notification(
        cls, form, row, values, users_to_notify, sender=None
    ):
        if not users_to_notify:
            return

        model = row._meta.model
        human_readable_values = []
        for form_field_option in form.formviewfieldoptions_set.order_by("order", "id"):
            field_instance = form_field_option.field
            field_name = field_instance.db_column
            if field_name not in values:
                continue
            field_object = model.get_field_object(field_name)
            field_type = field_object["type"]
            field_instance = field_object["field"]
            human_readable_field_value = field_type.get_human_readable_value(
                getattr(row, field_name), field_object
            )
            human_readable_values.append(
                [field_instance.name, human_readable_field_value]
            )

        # if the user is anonymous, we don't have a username to display in the
        # notification, so we set it to None
        if isinstance(sender, AnonymousUser):
            sender = None

        notification_data = FormSubmittedNotificationData(
            form.id,
            form.name,
            form.table.id,
            form.table.name,
            form.table.database_id,
            row.id,
            human_readable_values,
        )

        return NotificationHandler.create_direct_notification_for_users(
            notification_type=cls.type,
            recipients=users_to_notify,
            sender=sender,
            data=asdict(notification_data),
            workspace=form.table.database.workspace,
        )

    @classmethod
    def get_notification_title_for_email(cls, notification, context):
        return _("%(form_name)s has been submitted in %(table_name)s") % {
            "form_name": notification.data["form_name"],
            "table_name": notification.data["table_name"],
        }

    @classmethod
    def get_notification_description_for_email(cls, notification, context):
        limit_values = 3
        value_summary = "\n\n".join(
            [
                "%s: %s" % (key, value)
                for key, value in notification.data["values"][:limit_values]
            ]
        )
        missing_fields = max(0, len(notification.data["values"]) - limit_values)
        if missing_fields > 0:
            value_summary += "\n\n\n" + ngettext(
                "and 1 more field",
                "and %(count)s more fields",
                missing_fields,
            ) % {
                "count": missing_fields,
            }
        return value_summary


@receiver(form_submitted)
def create_form_submitted_notification(sender, form, row, values, user, **kwargs):
    users_to_notify = form.users_to_notify_on_submit.all()
    if not users_to_notify:
        return

    # Ensure all users still have permissions on the table to see the notification
    allowed_users = CoreHandler().check_permission_for_multiple_actors(
        users_to_notify,
        CanReceiveNotificationOnSubmitFormViewOperationType.type,
        workspace=form.table.database.workspace,
        context=form,
    )

    FormSubmittedNotificationType.create_form_submitted_notification(
        form, row, values, allowed_users, sender=user
    )
