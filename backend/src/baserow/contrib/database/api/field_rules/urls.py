from django.urls import re_path

from baserow.core.feature_flags import FF_DATE_DEPENDENCY_V2, feature_flag_is_enabled

from .views import FieldRulesView, FieldRuleView

app_name = "baserow.contrib.database.api.field_rules"

urlpatterns = [
    re_path(r"^(?P<table_id>[0-9]+)/$", FieldRulesView.as_view(), name="list"),
    re_path(
        r"^(?P<table_id>[0-9]+)/rule/(?P<rule_id>[0-9]+)/$",
        FieldRuleView.as_view(),
        name="item",
    ),
]

if feature_flag_is_enabled(FF_DATE_DEPENDENCY_V2):
    from .views import InvalidRowsView

    urlpatterns.append(
        re_path(
            r"^(?P<table_id>[0-9]+)/invalid-rows/$",
            InvalidRowsView.as_view(),
            name="invalid_rows",
        )
    )
