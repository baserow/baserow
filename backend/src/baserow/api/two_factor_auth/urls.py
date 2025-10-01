from django.urls import re_path

from .views import ConfigureTwoFactorAuthView, DisableTwoFactorAuthView

app_name = "baserow.api.two_factor_auth"

urlpatterns = [
    re_path(
        r"^configuration/$",
        ConfigureTwoFactorAuthView.as_view(),
        name="configuration",
    ),
    re_path(
        r"^disable/$",
        DisableTwoFactorAuthView.as_view(),
        name="disable",
    ),
]
