from django.urls import re_path

from .views import (
    AsyncInstallTemplateView,
    InstallTemplateView,
    TemplatesView,
    TemplateView,
)

app_name = "baserow.api.templates"


urlpatterns = [
    re_path(
        r"install/(?P<workspace_id>[0-9]+)/(?P<template_id>[0-9]+)/$",
        InstallTemplateView.as_view(),
        name="install",
    ),
    re_path(
        r"install/(?P<workspace_id>[0-9]+)/(?P<template_id>[0-9]+)/async/$",
        AsyncInstallTemplateView.as_view(),
        name="install_async",
    ),
    re_path(r"(?P<slug>[\w-]+)/$", TemplateView.as_view(), name="item"),
    re_path(r"$", TemplatesView.as_view(), name="list"),
]
