from django.urls import re_path

from .views import ConfigureTwoFactorAuthView

app_name = "baserow.api.two_factor_auth"

urlpatterns = [
    re_path(
        r"^configuration/$",
        ConfigureTwoFactorAuthView.as_view(),
        name="configuration",
    ),
]
