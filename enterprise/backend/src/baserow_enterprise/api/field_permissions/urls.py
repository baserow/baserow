from django.urls import re_path

from .views import FieldPermissionSubjectOptionsView, FieldPermissionsView

app_name = "baserow_enterprise.api.field_permissions"

urlpatterns = [
    re_path(r"^(?P<field_id>[0-9]+)/$", FieldPermissionsView.as_view(), name="item"),
    re_path(
        r"^(?P<field_id>[0-9]+)/subjects/$",
        FieldPermissionSubjectOptionsView.as_view(),
        name="subject_options",
    ),
]
