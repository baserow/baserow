from django.urls import include, path

from baserow.contrib.integrations.core.api.webhooks import urls

app_name = "baserow.contrib.integrations.api.core"

urlpatterns = [
    path("", include(urls, namespace="webhooks")),
]
