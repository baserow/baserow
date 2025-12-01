from django.urls import re_path

from .views import FieldPermissionsView

app_name = "baserow_enterprise.api.field_permissions"

urlpatterns = [
    re_path(r"^(?P<field_id>[0-9]+)/$", FieldPermissionsView.as_view(), name="item")
]
