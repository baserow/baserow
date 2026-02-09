from django.urls import re_path

from .views import FieldRulesView, FieldRuleView, InvalidRowsView

app_name = "baserow.contrib.database.api.field_rules"


urlpatterns = [
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
