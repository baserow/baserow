from django.urls import re_path

from baserow.contrib.database.fields.registries import field_type_registry

from .views import (
    AsyncDuplicateFieldView,
    ChangePrimaryFieldView,
    FieldsView,
    FieldView,
    PasswordFieldAuthenticationView,
    UniqueRowValueFieldView,
)

app_name = "baserow.contrib.database.api.fields"

urlpatterns = field_type_registry.api_urls + [
    re_path(r"table/(?P<table_id>[0-9]+)/$", FieldsView.as_view(), name="list"),
    re_path(
        r"table/(?P<table_id>[0-9]+)/change-primary-field/$",
        ChangePrimaryFieldView.as_view(),
        name="change_primary_field",
    ),
    re_path(
        r"(?P<field_id>[0-9]+)/unique_row_values/$",
        UniqueRowValueFieldView.as_view(),
        name="unique_row_values",
    ),
    re_path(r"(?P<field_id>[0-9]+)/$", FieldView.as_view(), name="item"),
    re_path(
        r"(?P<field_id>[0-9]+)/duplicate/async/$",
        AsyncDuplicateFieldView.as_view(),
        name="async_duplicate",
    ),
    re_path(
        r"password-authentication/$",
        PasswordFieldAuthenticationView.as_view(),
        name="password_authentication",
    ),
]
