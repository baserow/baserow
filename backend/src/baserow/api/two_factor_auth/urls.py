from django.urls import re_path

from .views import TwoFactorAuthView


urlpatterns = [
    re_path(
        r"^two-factor-auth/$",
        TwoFactorAuthView.as_view(),
        name="two_factor_auth",
    ),
]


app_name = "baserow.api.two_factor_auth"
