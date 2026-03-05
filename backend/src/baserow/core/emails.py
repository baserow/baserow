import re
from email.utils import make_msgid
from typing import List

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.translation import gettext as _

from loguru import logger

from baserow.core.notifications.models import Notification
from baserow.core.notifications.registries import notification_type_registry
from baserow.core.registries import email_context_registry


class BaseEmailMessage(EmailMultiAlternatives):
    """
    The base email message class can be used to create reusable email classes for
    each email. The template_name is rendered to a string and attached as html
    alternative. This content is automatically converted to plain text. The get_context
    method can be extended to add additional context variables while rendering the
    template.

    Example:
        class TestEmail(BaseEmailMessage):
            subject = 'Example subject'
            template_name = 'baserow/core/example.html'

        email = TestEmail(['test@localhost'])
        email.send()
    """

    subject = None
    template_name = None

    def __init__(self, to, from_email=None):
        if not from_email:
            from_email = self.get_from_email()

        subject = self.get_subject()
        template_name = self.get_template_name()
        context = self.get_context()
        html_content = render_to_string(template_name, context)

        text_content = self._get_plain_text_from_html(html_content)

        super().__init__(
            subject=subject, body=text_content, from_email=from_email, to=to
        )
        self.extra_headers["Message-ID"] = make_msgid(
            domain=settings.EMAIL_MESSAGE_ID_DOMAIN
        )
        self.attach_alternative(html_content, "text/html")

    @staticmethod
    def _get_plain_text_from_html(html_content):
        body_start_index = html_content.index("<body")
        body_end_index = html_content.index("</body>")
        body_with_no_tags = strip_tags(html_content[body_start_index:body_end_index])
        body_with_collapsed_spaces = re.compile(r" +").sub(" ", body_with_no_tags)
        body_without_blank_lines = re.compile(r"\n ").sub(
            "\n", body_with_collapsed_spaces
        )
        body_with_collapsed_newlines = re.compile(r"\n+").sub(
            "\n", body_without_blank_lines
        )
        return body_with_collapsed_newlines

    def get_context(self):
        return email_context_registry.get_context()

    def get_from_email(self):
        return settings.FROM_EMAIL

    def get_subject(self):
        if not self.subject:
            raise NotImplementedError("The subject must be implement.")
        return self.subject

    def get_template_name(self):
        if not self.template_name:
            raise NotImplementedError("The template_name must be implement.")
        return self.template_name

    def send(self, fail_silently=False):
        s = super()
        transaction.on_commit(lambda: s.send(fail_silently))


class EmailPendingVerificationEmail(BaseEmailMessage):
    template_name = "baserow/core/user/email_pending_verification.html"

    def __init__(self, confirm_url, *args, **kwargs):
        self.confirm_url = confirm_url
        super().__init__(*args, **kwargs)

    def get_subject(self):
        return _("Please confirm email")

    def get_context(self):
        context = super().get_context()
        context.update(confirm_url=self.confirm_url)
        return context


class WorkspaceInvitationEmail(BaseEmailMessage):
    template_name = "baserow/core/workspace_invitation.html"

    def __init__(self, invitation, public_accept_url, *args, **kwargs):
        self.public_accept_url = public_accept_url
        self.invitation = invitation
        super().__init__(*args, **kwargs)

    def get_subject(self):
        return _(
            "%(by)s invited you to %(workspace_name)s - Baserow",
        ) % {
            "by": self.invitation.invited_by.first_name,
            "workspace_name": self.invitation.workspace.name,
        }

    def get_context(self):
        context = super().get_context()
        context.update(
            invitation=self.invitation, public_accept_url=self.public_accept_url
        )
        return context


class NotificationsSummaryEmail(BaseEmailMessage):
    template_name = "baserow/core/notifications_summary.html"

    def __init__(
        self,
        to: List[str],
        notifications: List[Notification],
        new_notifications_count: int,
        *args,
        **kwargs,
    ):
        self.notifications = notifications
        self.new_notifications_count = new_notifications_count
        super().__init__(to, *args, **kwargs)

    def get_subject(self):
        count = self.new_notifications_count

        if count == 1:
            return _("You have 1 new notification - Baserow")

        return _("You have %(count)d new notifications - Baserow") % {"count": count}

    def get_context(self):
        context = super().get_context()
        rendered_notifications = []
        for notification in self.notifications:
            notification_type = notification_type_registry.get(notification.type)
            if not notification_type.include_in_notifications_email:
                logger.error(
                    f"Notification type {notification_type.type} cannot be included "
                    f"in the notifications email but it was included in the query. This "
                    f"shouldn't happen."
                )
                continue

            email_title = notification_type.get_notification_title_for_email(
                notification, context
            )
            email_description = (
                notification_type.get_notification_description_for_email(
                    notification, context
                )
            )
            email_url = notification_type.get_web_frontend_url(notification)
            rendered_notifications.append(
                {
                    "title": email_title,
                    "description": email_description,
                    "url": email_url,
                }
            )
        unlisted_notifications_count = self.new_notifications_count - len(
            rendered_notifications
        )
        context.update(
            notifications=rendered_notifications,
            new_notifications_count=self.new_notifications_count,
            unlisted_notifications_count=unlisted_notifications_count,
        )
        return context
