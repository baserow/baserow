from django.conf import settings
from django.utils.translation import gettext as _

from baserow.core.emails import BaseEmailMessage


class ResetPasswordEmail(BaseEmailMessage):
    template_name = "baserow/core/user/reset_password.html"

    def __init__(self, user, reset_url, *args, **kwargs):
        self.reset_url = reset_url
        self.user = user
        super().__init__(*args, **kwargs)

    def get_subject(self):
        return _("Reset password - Baserow")

    def get_context(self):
        context = super().get_context()
        context.update(
            user=self.user,
            reset_url=self.reset_url,
            expire_hours=settings.RESET_PASSWORD_TOKEN_MAX_AGE / 60 / 60,
        )
        return context


class AccountDeletionScheduled(BaseEmailMessage):
    template_name = "baserow/core/user/account_deletion_scheduled.html"

    def __init__(self, user, days_left, *args, **kwargs):
        self.days_left = days_left
        self.user = user
        super().__init__(*args, **kwargs)

    def get_subject(self):
        return _("Account deletion scheduled - Baserow")

    def get_context(self):
        context = super().get_context()
        context.update(
            user=self.user,
            days_left=self.days_left,
        )
        return context


class AccountDeleted(BaseEmailMessage):
    template_name = "baserow/core/user/account_deleted.html"

    def __init__(self, username, *args, **kwargs):
        self.username = username
        super().__init__(*args, **kwargs)

    def get_subject(self):
        return _("Account permanently deleted - Baserow")

    def get_context(self):
        context = super().get_context()
        context.update(
            username=self.username,
        )
        return context


class AccountDeletionCanceled(BaseEmailMessage):
    template_name = "baserow/core/user/account_deletion_cancelled.html"

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def get_subject(self):
        return _("Account deletion cancelled - Baserow")

    def get_context(self):
        context = super().get_context()
        context.update(
            user=self.user,
        )
        return context


class ChangeEmailConfirmationEmail(BaseEmailMessage):
    template_name = "baserow/core/user/change_email_confirmation.html"

    def __init__(self, user, new_email, confirmation_url, *args, **kwargs):
        self.user = user
        self.new_email = new_email
        self.confirmation_url = confirmation_url
        super().__init__(*args, **kwargs)

    def get_subject(self):
        return _("Confirm email address change - Baserow")

    def get_context(self):
        context = super().get_context()
        context.update(
            user=self.user,
            new_email=self.new_email,
            confirmation_url=self.confirmation_url,
            expire_hours=settings.CHANGE_EMAIL_TOKEN_MAX_AGE / 60 / 60,
        )
        return context
