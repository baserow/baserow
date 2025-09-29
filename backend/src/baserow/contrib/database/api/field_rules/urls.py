from django.urls import re_path

from baserow.core.feature_flags import FF_DATE_DEPENDENCY, feature_flag_is_enabled

app_name = "baserow.contrib.database.api.field_rules"

urlpatterns = []

if feature_flag_is_enabled(FF_DATE_DEPENDENCY):
    from .views import FieldRulesView, FieldRuleView, InvalidRowsView

    urlpatterns += [
        re_path(r"^(?P<table_id>[0-9]+)/$", FieldRulesView.as_view(), name="list"),
        re_path(
            r"^(?P<table_id>[0-9]+)/rule/(?P<rule_id>[0-9]+)/$",
            FieldRuleView.as_view(),
            name="item",
        ),
        re_path(
            r"^(?P<table_id>[0-9]+)/invalid-rows/$",
            InvalidRowsView.as_view(),
            name="invalid_rows",
        ),
    ]
