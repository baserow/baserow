from django.urls import re_path

from .views import (
    AccountView,
    BlacklistJSONWebToken,
    ChangeEmailView,
    ChangePasswordView,
    DashboardView,
    ObtainJSONWebToken,
    RedoView,
    RefreshJSONWebToken,
    ResetPasswordView,
    ScheduleAccountDeletionView,
    SendChangeEmailConfirmationView,
    SendResetPasswordEmailView,
    SendVerifyEmailView,
    ShareOnboardingDetailsWithBaserowView,
    UndoView,
    UserView,
    VerifyEmailAddressView,
    VerifyJSONWebToken,
)

app_name = "baserow.api.user"

urlpatterns = [
    re_path(r"^account/$", AccountView.as_view(), name="account"),
    re_path(
        r"^schedule-account-deletion/$",
        ScheduleAccountDeletionView.as_view(),
        name="schedule_account_deletion",
    ),
    re_path(r"^token-auth/$", ObtainJSONWebToken.as_view(), name="token_auth"),
    re_path(r"^token-refresh/$", RefreshJSONWebToken.as_view(), name="token_refresh"),
    re_path(r"^token-verify/$", VerifyJSONWebToken.as_view(), name="token_verify"),
    re_path(
        r"^token-blacklist/$", BlacklistJSONWebToken.as_view(), name="token_blacklist"
    ),
    re_path(
        r"^send-reset-password-email/$",
        SendResetPasswordEmailView.as_view(),
        name="send_reset_password_email",
    ),
    re_path(r"^reset-password/$", ResetPasswordView.as_view(), name="reset_password"),
    re_path(
        r"^change-password/$", ChangePasswordView.as_view(), name="change_password"
    ),
    re_path(
        r"^send-change-email-confirmation/$",
        SendChangeEmailConfirmationView.as_view(),
        name="send_change_email_confirmation",
    ),
    re_path(r"^change-email/$", ChangeEmailView.as_view(), name="change_email"),
    re_path(
        r"^send-verify-email/$", SendVerifyEmailView.as_view(), name="send_verify_email"
    ),
    re_path(r"^verify-email/$", VerifyEmailAddressView.as_view(), name="verify_email"),
    re_path(r"^dashboard/$", DashboardView.as_view(), name="dashboard"),
    re_path(r"^undo/$", UndoView.as_view(), name="undo"),
    re_path(r"^redo/$", RedoView.as_view(), name="redo"),
    re_path(
        r"^share-onboarding-details-with-baserow/$",
        ShareOnboardingDetailsWithBaserowView.as_view(),
        name="share_onboarding_details_with_baserow",
    ),
    re_path(r"^$", UserView.as_view(), name="index"),
]
