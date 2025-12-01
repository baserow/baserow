from django.urls import re_path

from baserow.contrib.database.views.registries import view_type_registry

from .views import (
    DuplicateViewView,
    OrderViewsView,
    PublicViewAuthView,
    PublicViewGetRowView,
    PublicViewInfoView,
    PublicViewLinkRowFieldLookupView,
    RotateViewSlugView,
    ViewDecorationsView,
    ViewDecorationView,
    ViewFieldOptionsView,
    ViewFilterGroupsView,
    ViewFilterGroupView,
    ViewFiltersView,
    ViewFilterView,
    ViewGroupBysView,
    ViewGroupByView,
    ViewSortingsView,
    ViewSortView,
    ViewsView,
    ViewView,
)

app_name = "baserow.contrib.database.api.views"

urlpatterns = view_type_registry.api_urls + [
    re_path(r"table/(?P<table_id>[0-9]+)/$", ViewsView.as_view(), name="list"),
    re_path(
        r"table/(?P<table_id>[0-9]+)/order/$", OrderViewsView.as_view(), name="order"
    ),
    re_path(
        r"(?P<slug>[-\w]+)/link-row-field-lookup/(?P<field_id>[0-9]+)/$",
        PublicViewLinkRowFieldLookupView.as_view(),
        name="link_row_field_lookup",
    ),
    re_path(
        r"filter/(?P<view_filter_id>[0-9]+)/$",
        ViewFilterView.as_view(),
        name="filter_item",
    ),
    re_path(
        r"filter-group/(?P<view_filter_group_id>[0-9]+)/$",
        ViewFilterGroupView.as_view(),
        name="filter_group_item",
    ),
    re_path(
        r"sort/(?P<view_sort_id>[0-9]+)/$", ViewSortView.as_view(), name="sort_item"
    ),
    re_path(
        r"group_by/(?P<view_group_by_id>[0-9]+)/$",
        ViewGroupByView.as_view(),
        name="group_by_item",
    ),
    re_path(
        r"decoration/(?P<view_decoration_id>[0-9]+)/$",
        ViewDecorationView.as_view(),
        name="decoration_item",
    ),
    re_path(r"(?P<view_id>[0-9]+)/$", ViewView.as_view(), name="item"),
    re_path(
        r"(?P<view_id>[0-9]+)/duplicate/$",
        DuplicateViewView.as_view(),
        name="duplicate",
    ),
    re_path(
        r"(?P<view_id>[0-9]+)/filters/$", ViewFiltersView.as_view(), name="list_filters"
    ),
    re_path(
        r"(?P<view_id>[0-9]+)/filter-groups/$",
        ViewFilterGroupsView.as_view(),
        name="list_filter_groups",
    ),
    re_path(
        r"(?P<view_id>[0-9]+)/sortings/$",
        ViewSortingsView.as_view(),
        name="list_sortings",
    ),
    re_path(
        r"(?P<view_id>[0-9]+)/group_bys/$",
        ViewGroupBysView.as_view(),
        name="list_group_bys",
    ),
    re_path(
        r"(?P<view_id>[0-9]+)/decorations/$",
        ViewDecorationsView.as_view(),
        name="list_decorations",
    ),
    re_path(
        r"(?P<view_id>[0-9]+)/field-options/$",
        ViewFieldOptionsView.as_view(),
        name="field_options",
    ),
    re_path(
        r"(?P<view_id>[0-9]+)/rotate-slug/$",
        RotateViewSlugView.as_view(),
        name="rotate_slug",
    ),
    re_path(
        r"(?P<slug>[-\w]+)/public/auth/$",
        PublicViewAuthView.as_view(),
        name="public_auth",
    ),
    re_path(
        r"(?P<slug>[-\w]+)/public/info/$",
        PublicViewInfoView.as_view(),
        name="public_info",
    ),
    re_path(
        r"(?P<slug>[-\w]+)/row/(?P<row_id>[0-9]+)/$",
        PublicViewGetRowView.as_view(),
        name="public_row",
    ),
]
