from django.urls import re_path

from baserow.api.admin.templates.views import (
    AdminApproveUserTemplateView,
    AdminRejectUserTemplateView,
    AdminUserTemplateCountsView,
    AdminUserTemplatesView,
)

app_name = "baserow.api.admin.templates"

urlpatterns = [
    re_path(r"^$", AdminUserTemplatesView.as_view(), name="list"),
    re_path(r"^counts/$", AdminUserTemplateCountsView.as_view(), name="counts"),
    re_path(
        r"^(?P<template_id>[0-9]+)/approve/$",
        AdminApproveUserTemplateView.as_view(),
        name="approve",
    ),
    re_path(
        r"^(?P<template_id>[0-9]+)/reject/$",
        AdminRejectUserTemplateView.as_view(),
        name="reject",
    ),
]
