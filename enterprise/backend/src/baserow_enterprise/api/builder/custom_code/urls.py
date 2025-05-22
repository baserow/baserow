from django.urls import re_path

from .views import CustomCodeView, PublicCustomCodeView

app_name = "baserow_enterprise.api.custom_code"

urlpatterns = [
    re_path(
        r"^(?P<builder_id>[0-9]+)/css/$",
        CustomCodeView.as_view(),
        {"code_type": "css"},
        name="css",
    ),
    re_path(
        r"^(?P<builder_id>[0-9]+)/js/$",
        CustomCodeView.as_view(),
        {"code_type": "js"},
        name="js",
    ),
    re_path(
        r"^(?P<builder_id>[0-9]+)/css/public/$",
        PublicCustomCodeView.as_view(),
        {"code_type": "css"},
        name="public_css",
    ),
    re_path(
        r"^(?P<builder_id>[0-9]+)/js/public/$",
        PublicCustomCodeView.as_view(),
        {"code_type": "js"},
        name="public_js",
    ),
]
